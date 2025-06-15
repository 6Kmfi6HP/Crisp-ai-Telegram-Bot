import json
import sqlite3
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import os

class SessionPersistence:
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('persistence', {})
        self.storage_type = self.config.get('storage_type', 'json')
        self.data_file = self.config.get('data_file', 'session_data.db')
        self.expire_days = self.config.get('expire_days', 14)
        
        # 异步保存配置
        self.async_config = self.config.get('async_save', {})
        self.async_enabled = self.async_config.get('enabled', True)
        self.batch_interval = self.async_config.get('batch_interval', 30)
        self.max_batch_size = self.async_config.get('max_batch_size', 100)
        
        # 内存中的待保存数据
        self._pending_saves = {}
        self._save_lock = threading.Lock()
        self._save_task = None
        
        # 初始化存储
        self._init_storage()
        
        # 启动异步保存任务
        if self.async_enabled:
            self._start_async_save_task()
    
    def _init_storage(self):
        """初始化存储系统"""
        if self.storage_type == 'sqlite':
            self._init_sqlite()
        elif self.storage_type == 'json':
            self._init_json()
    
    def _init_sqlite(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.data_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                topic_id INTEGER,
                message_id INTEGER,
                enable_ai BOOLEAN,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def _init_json(self):
        """初始化JSON文件"""
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def load_session_data(self) -> Dict[str, Any]:
        """加载会话数据"""
        try:
            if self.storage_type == 'sqlite':
                return self._load_from_sqlite()
            else:
                return self._load_from_json()
        except Exception as e:
            logging.error(f"加载会话数据失败: {e}")
            return {}
    
    def _load_from_sqlite(self) -> Dict[str, Any]:
        """从SQLite加载数据"""
        conn = sqlite3.connect(self.data_file)
        cursor = conn.cursor()
        
        # 删除过期数据
        expire_date = datetime.now() - timedelta(days=self.expire_days)
        cursor.execute('DELETE FROM sessions WHERE last_updated < ?', (expire_date,))
        
        # 加载有效数据
        cursor.execute('SELECT session_id, topic_id, message_id, enable_ai FROM sessions')
        rows = cursor.fetchall()
        
        data = {}
        for row in rows:
            session_id, topic_id, message_id, enable_ai = row
            data[session_id] = {
                'topicId': topic_id,
                'messageId': message_id,
                'enableAI': bool(enable_ai)
            }
        
        conn.commit()
        conn.close()
        return data
    
    def _load_from_json(self) -> Dict[str, Any]:
        """从JSON文件加载数据"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 清理过期数据
            expire_date = datetime.now() - timedelta(days=self.expire_days)
            valid_data = {}
            
            for session_id, session_data in data.items():
                last_updated_str = session_data.get('last_updated')
                if last_updated_str:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    if last_updated > expire_date:
                        # 移除时间戳，保持原有格式
                        clean_data = {k: v for k, v in session_data.items() if k != 'last_updated'}
                        valid_data[session_id] = clean_data
            
            # 保存清理后的数据
            if len(valid_data) != len(data):
                self._save_to_json_sync(valid_data)
            
            return valid_data
        except FileNotFoundError:
            return {}
    
    def save_session_data(self, session_id: str, session_data: Dict[str, Any]):
        """保存会话数据"""
        if self.async_enabled:
            self._queue_for_async_save(session_id, session_data)
        else:
            self._save_immediately(session_id, session_data)
    
    def _queue_for_async_save(self, session_id: str, session_data: Dict[str, Any]):
        """将数据加入异步保存队列"""
        with self._save_lock:
            self._pending_saves[session_id] = {
                **session_data,
                'last_updated': datetime.now().isoformat()
            }
    
    def _save_immediately(self, session_id: str, session_data: Dict[str, Any]):
        """立即保存数据"""
        try:
            if self.storage_type == 'sqlite':
                self._save_to_sqlite(session_id, session_data)
            else:
                # 对于JSON，需要加载全部数据再保存
                all_data = self._load_from_json()
                all_data[session_id] = session_data
                self._save_to_json_sync(all_data)
        except Exception as e:
            logging.error(f"保存会话数据失败: {e}")
    
    def _save_to_sqlite(self, session_id: str, session_data: Dict[str, Any]):
        """保存到SQLite"""
        conn = sqlite3.connect(self.data_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO sessions 
            (session_id, topic_id, message_id, enable_ai, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            session_id,
            session_data.get('topicId'),
            session_data.get('messageId'),
            session_data.get('enableAI', False)
        ))
        
        conn.commit()
        conn.close()
    
    def _save_to_json_sync(self, all_data: Dict[str, Any]):
        """同步保存到JSON文件"""
        # 添加时间戳
        timestamped_data = {}
        for session_id, session_data in all_data.items():
            timestamped_data[session_id] = {
                **session_data,
                'last_updated': datetime.now().isoformat()
            }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(timestamped_data, f, ensure_ascii=False, indent=2)
    
    def _start_async_save_task(self):
        """启动异步保存任务"""
        def save_worker():
            while True:
                try:
                    # 等待指定间隔
                    threading.Event().wait(self.batch_interval)
                    
                    # 获取待保存的数据
                    with self._save_lock:
                        if not self._pending_saves:
                            continue
                        
                        # 限制批量大小
                        items_to_save = dict(list(self._pending_saves.items())[:self.max_batch_size])
                        
                        # 清空已处理的项目
                        for session_id in items_to_save.keys():
                            del self._pending_saves[session_id]
                    
                    # 批量保存
                    if items_to_save:
                        self._batch_save(items_to_save)
                        
                except Exception as e:
                    logging.error(f"异步保存任务错误: {e}")
        
        # 启动后台线程
        save_thread = threading.Thread(target=save_worker, daemon=True)
        save_thread.start()
    
    def _batch_save(self, items_to_save: Dict[str, Any]):
        """批量保存数据"""
        try:
            if self.storage_type == 'sqlite':
                self._batch_save_sqlite(items_to_save)
            else:
                self._batch_save_json(items_to_save)
        except Exception as e:
            logging.error(f"批量保存失败: {e}")
    
    def _batch_save_sqlite(self, items_to_save: Dict[str, Any]):
        """批量保存到SQLite"""
        conn = sqlite3.connect(self.data_file)
        cursor = conn.cursor()
        
        for session_id, session_data in items_to_save.items():
            cursor.execute('''
                INSERT OR REPLACE INTO sessions 
                (session_id, topic_id, message_id, enable_ai, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session_id,
                session_data.get('topicId'),
                session_data.get('messageId'),
                session_data.get('enableAI', False),
                session_data.get('last_updated', datetime.now().isoformat())
            ))
        
        conn.commit()
        conn.close()
    
    def _batch_save_json(self, items_to_save: Dict[str, Any]):
        """批量保存到JSON"""
        # 加载现有数据
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            all_data = {}
        
        # 更新数据
        all_data.update(items_to_save)
        
        # 保存回文件
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    def clean_expired_data(self):
        """清理过期数据"""
        try:
            if self.storage_type == 'sqlite':
                self._clean_expired_sqlite()
            else:
                self._clean_expired_json()
            logging.info("过期数据清理完成")
        except Exception as e:
            logging.error(f"清理过期数据失败: {e}")
    
    def _clean_expired_sqlite(self):
        """清理SQLite中的过期数据"""
        conn = sqlite3.connect(self.data_file)
        cursor = conn.cursor()
        
        expire_date = datetime.now() - timedelta(days=self.expire_days)
        cursor.execute('DELETE FROM sessions WHERE last_updated < ?', (expire_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logging.info(f"清理了 {deleted_count} 条过期会话数据")
    
    def _clean_expired_json(self):
        """清理JSON中的过期数据"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        
        expire_date = datetime.now() - timedelta(days=self.expire_days)
        valid_data = {}
        deleted_count = 0
        
        for session_id, session_data in data.items():
            last_updated_str = session_data.get('last_updated')
            if last_updated_str:
                try:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    if last_updated > expire_date:
                        valid_data[session_id] = session_data
                    else:
                        deleted_count += 1
                except ValueError:
                    # 如果时间格式有问题，保留数据但添加新的时间戳
                    session_data['last_updated'] = datetime.now().isoformat()
                    valid_data[session_id] = session_data
            else:
                # 没有时间戳的数据，添加时间戳并保留
                session_data['last_updated'] = datetime.now().isoformat()
                valid_data[session_id] = session_data
        
        if deleted_count > 0:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(valid_data, f, ensure_ascii=False, indent=2)
            logging.info(f"清理了 {deleted_count} 条过期会话数据")
    
    def force_save_pending(self):
        """强制保存所有待保存的数据"""
        with self._save_lock:
            if self._pending_saves:
                self._batch_save(self._pending_saves.copy())
                self._pending_saves.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        stats = {
            'storage_type': self.storage_type,
            'data_file': self.data_file,
            'expire_days': self.expire_days,
            'async_enabled': self.async_enabled
        }
        
        if self.storage_type == 'sqlite':
            try:
                conn = sqlite3.connect(self.data_file)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM sessions')
                stats['total_sessions'] = cursor.fetchone()[0]
                conn.close()
            except Exception:
                stats['total_sessions'] = 0
        else:
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats['total_sessions'] = len(data)
            except Exception:
                stats['total_sessions'] = 0
        
        with self._save_lock:
            stats['pending_saves'] = len(self._pending_saves)
        
        return stats