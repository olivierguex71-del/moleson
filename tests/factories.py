"""Fabriques d'objets pour les tests.

Toutes les valeurs sont **inventées et déterministes** — pas de Faker, pas
d'extrait d'export Welante. Un jeu de test doit pouvoir circuler entre machines
et apparaître dans un journal sans exposer la moindre donnée personnelle réelle
(nLPD).
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.catalog.models import (
    Course,
    CourseSession,
    Location,
    Period,
    PeriodKind,
    Region,
    Room,
    Subject,
)
from apps.contacts.models import Contact, Membership, MembershipType, Salutation, Trainer
from apps.enrolments.models import Enrolment, EnrolmentStatus

#: IBAN de test à clé de contrôle valide, sur un numéro de compte fictif.
IBAN_DE_TEST = "CH9300762011623852957"


class ContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contact

    salutation = Salutation.MADAM
    first_name = factory.Sequence(lambda n: f"Prénom{n}")
    last_name = factory.Sequence(lambda n: f"Nomdetest{n}")
    email = factory.Sequence(lambda n: f"contact{n}@example.invalid")
    correspondence_language = "fr"
    street = "Rue de l'Exemple"
    house_number = "1"
    postal_code = "1700"
    city = "Fribourg"


class MembershipTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MembershipType
        django_get_or_create = ("code",)

    code = "actif"
    name_fr = "Membre actif"
    name_de = "Aktivmitglied"
    discount_percent = Decimal("10")


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    contact = factory.SubFactory(ContactFactory)
    type = factory.SubFactory(MembershipTypeFactory)
    starts_on = date(2026, 1, 1)
    ends_on = None


class TrainerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Trainer

    contact = factory.SubFactory(ContactFactory)
    iban = IBAN_DE_TEST
    bank_name = "Banque fictive"


class RegionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Region
        django_get_or_create = ("code",)

    code = "FR"
    slug = factory.LazyAttribute(lambda o: o.code.lower())
    name_fr = "Sarine"
    name_de = "Saane"
    main_city = "Fribourg"


class PeriodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Period
        django_get_or_create = ("year", "kind")

    year = 2026
    kind = PeriodKind.T4
    starts_on = date(2026, 9, 1)
    ends_on = date(2026, 12, 20)


class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject

    slug = factory.Sequence(lambda n: f"matiere-{n}")
    name_fr = factory.Sequence(lambda n: f"Matière {n}")
    name_de = factory.Sequence(lambda n: f"Fach {n}")


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Sequence(lambda n: f"Lieu de test {n}")
    postal_code = "1700"
    city = "Fribourg"


class RoomFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Room

    location = factory.SubFactory(LocationFactory)
    name = factory.Sequence(lambda n: f"Salle {n}")
    capacity = 12


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    code = factory.Sequence(lambda n: f"2026-T4-44{n:04d}-FR")
    period = factory.SubFactory(PeriodFactory)
    region = factory.SubFactory(RegionFactory)
    title_fr = "Anglais niveau A1"
    title_de = "Englisch Stufe A1"
    base_price = Decimal("300.00")


class CourseSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CourseSession

    course = factory.SubFactory(CourseFactory)
    starts_at = factory.LazyFunction(
        lambda: timezone.make_aware(datetime.combine(date(2026, 9, 15), time(18, 0)))
    )
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + timedelta(hours=2))


class EnrolmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Enrolment

    course = factory.SubFactory(CourseFactory)
    participant = factory.SubFactory(ContactFactory)
    status = EnrolmentStatus.CONFIRMED
    enrolled_on = date(2026, 9, 1)
