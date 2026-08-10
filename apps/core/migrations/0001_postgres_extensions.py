"""Extensions PostgreSQL dont dépend Moléson.

- `unaccent` : recherche insensible aux accents, indispensable en contexte FR/DE
  (« Glâne » doit se trouver en tapant « Glane », « Düdingen » en tapant « Dudingen »).
- `pg_trgm` : similarité par trigrammes, socle de la détection de doublons à la
  saisie d'un contact (nom, email, adresse proches).

Ces deux extensions justifient à elles seules le choix de PostgreSQL : sans elles,
il faudrait un moteur de recherche externe pour quelques centaines de contacts.

La création d'une extension exige des droits élevés sur la base. C'est le cas de
l'utilisateur créé par l'image officielle `postgres`, en développement comme sur
le VPS.
"""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        UnaccentExtension(),
        TrigramExtension(),
    ]
