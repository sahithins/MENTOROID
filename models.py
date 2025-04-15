from flask_mongoengine import MongoEngine
from datetime import datetime, timedelta
from mongoengine import (
    Document, EmbeddedDocument,
    StringField, DateTimeField, ListField, IntField,
    ReferenceField, CASCADE, BooleanField, EmbeddedDocumentField
)

db = MongoEngine()

class User(Document):
    fullname = StringField(required=True)
    password = StringField(required=True)
    age = IntField(required=True)
    phonenumber = StringField(required=True)
    email = StringField(required=True, unique=True)
    address = StringField(required=True)
    image_file = StringField(default="default.jpg")
    role = StringField(default="user")

    def __repr__(self):
        return f"User('{self.fullname}', '{self.email}', '{self.image_file}')"

class Mentor(Document):
    fullname = StringField(required=True)
    password = StringField(required=True)
    email = StringField(required=True, unique=True)
    phonenumber = StringField(required=True)
    image_file = StringField(default="default.jpg")
    qualification = StringField()
    experience = StringField()
    linkedin = StringField()
    resume_file = StringField()
    status = BooleanField(default=False)

    def get_resume_url(self):
        return self.resume_file if self.resume_file else None

    def __repr__(self):
        return f"Mentor('{self.fullname}', '{self.email}', '{self.qualification}')"

class Courses(Document):
    course_name = StringField(required=True)
    course_category = StringField()
    mentor_email = StringField()
    summary = StringField(required=True)
    course_image = StringField()

    def __repr__(self):
        return f"Courses('{self.course_name}', '{self.summary}')"

class Unit(Document):
    title = StringField(required=True)
    course = ReferenceField(Courses, reverse_delete_rule=CASCADE, required=True)
    order = IntField(default=0)

    meta = {'indexes': ['course', 'order']}

    def __repr__(self):
        return f"Unit('{self.title}', Course: '{self.course.course_name}')"

class Lesson(Document):
    title = StringField(required=True)
    unit = ReferenceField(Unit, reverse_delete_rule=CASCADE, required=True)
    file_type = StringField(required=True, choices=('Video', 'Material', 'Quiz', 'Assignment'))
    description = StringField()
    upload_file = StringField()
    external_url = StringField()
    order = IntField(default=0)
    date_uploaded = DateTimeField(default=datetime.utcnow)

    meta = {'indexes': ['unit', 'order']}

    def __repr__(self):
        return f"Lesson('{self.title}', Unit: '{self.unit.title}')"

class Enrollment(Document):
    user_id = StringField(required=True)
    course = ReferenceField(Courses, reverse_delete_rule=CASCADE, required=True)
    enrollment_date = DateTimeField(default=datetime.utcnow)
    expire_date = DateTimeField()
    status = StringField(default="active")

    meta = {'indexes': ['user_id', 'course']}

    def __repr__(self):
        return f"Enrollment(user_id: {self.user_id}, course: {self.course.course_name}, status: {self.status})"

    @classmethod
    def update_enrollment_status(cls):
        now = datetime.utcnow()
        cls.objects(expire_date__lt=now, status="active").update(set__status="expired")

class Question(EmbeddedDocument):
    text = StringField(required=True)
    options = ListField(StringField(), required=True)
    correct_option = IntField(required=True, min_value=0)

    def __repr__(self):
        return f"Question(text='{self.text[:30]}...', options={len(self.options)})"

class Quiz(Document):
    course = ReferenceField(Courses, reverse_delete_rule=CASCADE, required=True, unique=True)
    title = StringField(required=True, default="Final Quiz")
    questions = ListField(EmbeddedDocumentField(Question), default=[])
    passing_score_percent = IntField(default=70, min_value=0, max_value=100)

    meta = {'indexes': ['course']}

    def __repr__(self):
        return f"Quiz(course='{self.course.course_name}', questions={len(self.questions)})"

class CompletionStatus(Document):
    user_email = StringField(required=True)
    course = ReferenceField(Courses, required=True)
    completed_lessons = ListField(ReferenceField(Lesson), default=[])
    quiz_taken = BooleanField(default=False)
    quiz_passed = BooleanField(default=False)
    quiz_score_percent = IntField(default=None)

    meta = {'indexes': ['user_email', 'course']}

    def __repr__(self):
        completed_ids = [str(lesson.id) for lesson in self.completed_lessons]
        quiz_status = (
            f"Quiz Taken: {self.quiz_taken}, Passed: {self.quiz_passed}, Score: {self.quiz_score_percent}%"
            if self.quiz_taken else "Quiz Not Taken"
        )
        return f"CompletionStatus(user={self.user_email}, course={self.course.course_name}, completed_ids={completed_ids}, {quiz_status})"

class Feedbacks(Document):
    user_name = StringField(required=True)
    user_email = StringField(required=True)
    mentor_name = StringField(required=True)
    course_name = StringField(required=True)
    course_category = StringField(required=True)
    rating = IntField(required=True, min_value=1, max_value=5)
    feedback = StringField(required=True)
    suggestions = StringField()
    timestamp = DateTimeField(default=datetime.utcnow)

    def __repr__(self):
        return f"Feedbacks({self.user_email}, {self.course_name}, Rating: {self.rating}/5)"

class Certificate(Document):
    user_email = StringField(required=True)
    course_name = StringField(required=True)
    completion_date = DateTimeField(required=True)

    meta = {'collection': 'certificates'}