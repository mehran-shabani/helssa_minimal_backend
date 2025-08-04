import os

import django

print("Setting up Django...")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medogram.settings')

django.setup()

print("Django has been set up.")

import factory
from telemedicine.models import CustomUser, Visit, Blog, Comment  # Import only necessary models


# CustomUser factory
class CustomUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CustomUser

    phone_number = factory.Faker('phone_number')
    username = factory.Faker('user_name')
    email = factory.Faker('email')
    is_active = True
    is_staff = False
    is_superuser = False


# Visit factory
class VisitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Visit

    user = factory.SubFactory(CustomUserFactory)
    name = factory.Faker('sentence', nb_words=3)
    urgency = factory.Iterator(['prescription', 'diet', 'addiction', 'online_consultation'])
    general_symptoms = factory.Iterator(['fever', 'fatigue', 'weight_loss'])
    neurological_symptoms = factory.Iterator(['headache', 'dizziness', 'seizures'], cycle=True)
    cardiovascular_symptoms = factory.Iterator(['chest_pain', 'palpitations'], cycle=True)
    gastrointestinal_symptoms = factory.Iterator(['nausea', 'vomiting'], cycle=True)
    respiratory_symptoms = factory.Iterator(['cough', 'shortness_of_breath'], cycle=True)
    description = factory.Faker('text')


# Blog factory
class BlogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Blog

    title = factory.Faker('sentence', nb_words=5)
    content = factory.Faker('paragraph', nb_sentences=3)
    author = factory.SubFactory(CustomUserFactory)
    created_at = factory.Faker('date_time_this_year')


# Comment factory
class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    user = factory.SubFactory(CustomUserFactory)
    comment = factory.Faker('sentence')
    blog = factory.SubFactory(BlogFactory)
    likes = factory.Faker('random_int', min=0, max=100)
    created_at = factory.Faker('date_time_this_year')


# Example of how to create test data

if __name__ == '__main__':
    # Create three distinct users manually
    user1 = CustomUserFactory()
    user2 = CustomUserFactory()
    user3 = CustomUserFactory()

    # Create visits for these three users
    for _ in range(5):
        VisitFactory(user=user1)
        VisitFactory(user=user2)
        VisitFactory(user=user3)

    # Create some additional users without visits
    for _ in range(7):
        CustomUserFactory()

    # Create blogs and comments for the users
    for _ in range(3):
        blog = BlogFactory()
        for _ in range(5):
            CommentFactory(blog=blog)
