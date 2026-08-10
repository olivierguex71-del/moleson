"""Extension `btree_gist`.

Permet de mêler une égalité (une salle, un contact) et un chevauchement
d'intervalle dans une même contrainte d'exclusion. C'est ce qui rend possible,
au niveau de la base :

- deux séances ne peuvent pas occuper la même salle au même moment ;
- un contact ne peut pas avoir deux adhésions actives simultanées.

Ces règles tiennent alors quel que soit le chemin d'écriture — administration,
API, script de migration —, là où un contrôle applicatif se contourne.
"""

from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0001_postgres_extensions")]

    operations = [BtreeGistExtension()]
