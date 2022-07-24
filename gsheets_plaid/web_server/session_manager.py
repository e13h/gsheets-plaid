from abc import ABC, abstractmethod
from typing import Any

from flask import Flask
from google.cloud import firestore


class SessionManager(ABC):
    def __init__(self) -> None:
        self.user_id = None

    def register_user_id(self, user_id: str) -> None:
        self.user_id = user_id
    
    def clear_session(self) -> None:
        self.user_id = None

    @abstractmethod
    def get_session(self) -> dict:
        raise NotImplementedError()

    @abstractmethod
    def set_session(self, data: dict) -> None:
        raise NotImplementedError()

    @abstractmethod
    def __getitem__(self, key: str) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def __setitem__(self, key: str, value: Any) -> None:
        raise NotImplementedError()
    
    @abstractmethod
    def __delitem__(self, key: str) -> None:
        raise NotImplementedError()


class FirestoreSessionManager(SessionManager):
    def __init__(self, firestore_client: firestore.Client) -> None:
        super().__init__()
        self.db = firestore_client
        self.users = self.db.collection('users')
        self.doc_ref = None

    def register_user_id(self, user_id: str) -> None:
        super().register_user_id(user_id)
        self.doc_ref = self.users.document(document_id=user_id)
        doc = self.doc_ref.get()
        if not doc.exists:
            self.doc_ref.set({})

    def clear_session(self) -> None:
        super().clear_session()
        self.doc_ref = None

    def get_session(self) -> dict:
        if not self.user_id:
            raise ValueError('Call register_user_id() first.')
        return self.doc_ref.get().to_dict()
    
    def set_session(self, data: dict) -> None:
        if not self.user_id:
            raise ValueError('Call register_user_id() first.')
        self.doc_ref.set(data)
    
    def __getitem__(self, key: str) -> Any:
        return self.get_session()[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.doc_ref.set({key: value}, merge=True)
    
    def __delitem__(self, key: str) -> None:
        self.doc_ref.update({key: firestore.DELETE_FIELD})


class FlaskSessionManager(SessionManager):
    def  __init__(self, session, secret_key: str = 'default') -> None:
        super().__init__()
        Flask.secret_key = secret_key
        self.session = session

    def register_user_id(self, user_id: str) -> None:
        super().register_user_id(user_id)
        if user_id not in self.session:
            self.session[user_id] = {}

    def get_session(self) -> dict:
        if not self.user_id:
            raise ValueError('Call register_user_id() first.')
        return self.session[self.user_id]

    def set_session(self, data: dict) -> None:
        if not self.user_id:
            raise ValueError('Call register_user_id() first.')
        self.session[self.user_id] = data
        # self.session.modified = True
    
    def __getitem__(self, key: str) -> Any:
        return self.get_session()[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.session[self.user_id][key] = value
        self.session.modified = True

    def __delitem__(self, key: str) -> None:
        del self.session[self.user_id][key]
        self.session.modified = True
