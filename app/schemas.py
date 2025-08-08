from marshmallow import Schema, fields, validate

class UserRegisterSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))

class UserLoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)

class AddSubjectSchema(Schema):
    subjecturl = fields.URL(required=True)

class ChatSchema(Schema):    
    chatbot_user_id = fields.Str(required=True)
    question = fields.Str(required=True, validate=validate.Length(min=1))
    subjectkey = fields.Str(required=True, validate=validate.Length(equal=32))


class ClearSessionSchema(Schema):
    chatbot_user_id = fields.Str(required=True)
