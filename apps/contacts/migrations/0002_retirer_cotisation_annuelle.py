"""Retrait de la cotisation annuelle des types d'adhésion.

Rien dans les exports Welante n'indique que l'Unipop facture ses adhésions par
cet outil. Un champ que personne ne remplit devient vite un champ auquel
quelqu'un finit par croire : il est retiré tant que le besoin n'est pas établi.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='membershiptype',
            name='annual_fee',
        ),
    ]
