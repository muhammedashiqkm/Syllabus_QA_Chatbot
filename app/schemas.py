from marshmallow import Schema, fields, validate

class UserRegisterSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))
    registration_secret = fields.Str(required=True)

class UserLoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

class ChatSchema(Schema):    
    chatbot_user_id = fields.Str(required=True)
    question = fields.Str(required=True, validate=validate.Length(min=1))
    syllabus = fields.Str(required=True)
    subject = fields.Str(required=True)
    class_name = fields.Str(required=True, data_key="class")

class ClearSessionSchema(Schema):
    chatbot_user_id = fields.Str(required=True)