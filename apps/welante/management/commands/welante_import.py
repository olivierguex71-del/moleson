"""Importe les exports Welante dans Moléson.

**Simulation par défaut.** Sans `--commit`, l'import s'exécute réellement —
écritures comprises — puis la transaction est annulée. La simulation éprouve
donc les vraies contraintes de la base : un chevauchement de salle ou une
adhésion en double échoue en simulation exactement comme il échouerait pour de
bon. Un mode qui se contenterait de compter les lignes sans écrire ne dirait
rien de ce qui compte.

L'ordre d'import n'est pas négociable : les cours ont besoin des catégories, les
inscriptions ont besoin des cours et des contacts.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.welante.columns import resolve_columns
from apps.welante.importers.categories import import_categories
from apps.welante.importers.courses import import_courses
from apps.welante.importers.members import import_members
from apps.welante.importers.participants import import_participants
from apps.welante.importers.trainers import import_trainers
from apps.welante.reports import ReportSet
from apps.welante.sources import find_sources
from apps.welante.workbook import WorkbookError, read_workbook

#: Ordre imposé par les dépendances entre entités.
IMPORTEURS = {
    "categories": import_categories,
    "trainers": import_trainers,
    "members": import_members,
    "courses": import_courses,
    "participants": import_participants,
}

#: Exports repris par défaut.
#:
#: Les inscriptions en sont exclues sur décision : le seul export disponible ne
#: contient que des lignes au statut « Copié » — la file de reconduction, que le
#: secrétariat traite dans Welante avant la bascule — et pointe vers des cours
#: de 2017 à 2026 absents de l'export des cours. Les importer produirait des
#: centaines de lignes rejetées sans rien apporter.
#:
#: L'importeur reste disponible via `--only participants` le jour où un export
#: complet des inscriptions et des cours de toutes les périodes sera fourni.
PAR_DEFAUT = ["categories", "trainers", "members", "courses"]


class Command(BaseCommand):
    help = "Importe les exports Welante (simulation par défaut, --commit pour écrire)."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="data", help="Dossier des exports.")
        parser.add_argument(
            "--only",
            action="append",
            choices=list(IMPORTEURS),
            help=(
                "N'importer que ces exports (répétable). Attention aux dépendances. "
                "Les inscriptions ne sont pas reprises par défaut."
            ),
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Écrire réellement. Sans ce drapeau, tout est annulé à la fin.",
        )
        parser.add_argument(
            "--report",
            help="Chemin d'un CSV d'anomalies à écrire (ne contient aucune valeur source).",
        )

    def handle(self, *args, **options):
        dossier = Path(options["source"])
        demandes = options["only"] or PAR_DEFAUT
        rapports = ReportSet()

        if erreur := self._configuration_manquante(demandes):
            self.stderr.write(self.style.ERROR(erreur))
            return

        if not options["commit"]:
            self.stdout.write(
                self.style.WARNING(
                    "SIMULATION — les écritures seront annulées à la fin. "
                    "Ajouter --commit pour importer réellement.\n"
                )
            )

        try:
            with transaction.atomic():
                self._importer(dossier, demandes, rapports)
                if not options["commit"]:
                    transaction.set_rollback(True)
        except WorkbookError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        self._afficher(rapports, options)

    @staticmethod
    def _configuration_manquante(demandes: list[str]) -> str:
        """Vérifie avant de commencer ce qui ferait échouer l'import en cours de route.

        L'export des intervenants contient des numéros AVS : sans clé de
        chiffrement, l'écriture échouerait au milieu du traitement. Mieux vaut
        refuser de démarrer que s'arrêter à la centième ligne.
        """
        if "trainers" not in demandes:
            return ""
        if [cle for cle in settings.MOLESON_ENCRYPTION_KEYS if cle.strip()]:
            return ""
        return (
            "MOLESON_ENCRYPTION_KEYS est vide, alors que l'export des intervenants "
            "contient des numéros AVS.\n"
            "Générer une clé et la placer dans .env :\n"
            '  docker compose run --rm app python -c "from cryptography.fernet import '
            'Fernet; print(Fernet.generate_key().decode())"\n'
            "Cette clé doit être sauvegardée séparément des sauvegardes de base : "
            "la perdre rend les numéros AVS définitivement illisibles."
        )

    def _importer(self, dossier: Path, demandes: list[str], rapports: ReportSet) -> None:
        fichiers = {fichier.source.key: fichier for fichier in find_sources(dossier)}

        for cle in IMPORTEURS:
            if cle not in demandes:
                continue

            fichier = fichiers[cle]
            if not fichier.exists:
                self.stdout.write(
                    self.style.WARNING(f"{fichier.source.label} : fichier absent, ignoré.")
                )
                continue

            source = fichier.source
            classeur = read_workbook(
                fichier.path, header_row=source.header_row, skip_rows=source.skip_rows
            )
            mapping = resolve_columns(classeur.headers, source.columns)

            if manquantes := mapping.missing_required:
                self.stderr.write(
                    self.style.ERROR(
                        f"{source.label} : colonnes requises introuvables "
                        f"({', '.join(colonne.name for colonne in manquantes)}). "
                        "Lancer `welante_inspect` et ajuster apps/welante/sources.py."
                    )
                )
                continue

            self.stdout.write(f"{source.label} — {fichier.path.name}")
            rapports.add(IMPORTEURS[cle](classeur, mapping))

    def _afficher(self, rapports: ReportSet, options: dict) -> None:
        self.stdout.write("")
        for ligne in rapports.summary_lines():
            self.stdout.write(ligne)

        if chemin := options.get("report"):
            destination = Path(chemin)
            for rapport in rapports.reports:
                suffixe = Path(rapport.source).stem
                rapport.write_csv(destination.with_name(f"{destination.stem}-{suffixe}.csv"))
            self.stdout.write(f"Anomalies écrites à côté de {destination}")

        if rapports.total_to_review:
            self.stdout.write(
                self.style.WARNING(
                    f"{rapports.total_to_review} point(s) demandent un arbitrage humain."
                )
            )

        if rapports.has_errors:
            self.stdout.write(self.style.ERROR("Des lignes n'ont pas pu être importées."))
        elif options["commit"]:
            self.stdout.write(self.style.SUCCESS("Import terminé."))
        else:
            self.stdout.write(self.style.SUCCESS("Simulation terminée, rien n'a été écrit."))
