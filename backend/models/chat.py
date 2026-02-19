import json

from backend.database import db


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="New Chat")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    messages = db.relationship("Message", backref="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    def to_dict(self, include_messages=False):
        d = {
            "id": self.id,
            "title": self.title,
            "created_at": (self.created_at.isoformat() + "+00:00") if self.created_at else None,
            "updated_at": (self.updated_at.isoformat() + "+00:00") if self.updated_at else None,
        }
        if include_messages:
            d["messages"] = [m.to_dict() for m in self.messages]
        return d


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "user" or "assistant"
    content = db.Column(db.Text, default="")
    tool_calls = db.Column(db.Text)  # JSON string of tool call data
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": json.loads(self.tool_calls) if self.tool_calls else None,
            "created_at": (self.created_at.isoformat() + "+00:00") if self.created_at else None,
        }
