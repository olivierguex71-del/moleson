"""Décrit la structure des exports Welante sans en exposer le contenu.

Première commande à lancer sur une machine où `data/` vient d'être recopié. Elle
répond à : les fichiers sont-ils là, quelles colonnes contiennent-ils, lesquelles
Moléson ne reconnaît pas ?

**Aucune valeur du fichier n'est affichée.** Seuls sortent des intitulés de
colonnes et des agrégats — nombre de lignes, taux de remplissage, nombre de
valeurs distinctes. La sortie peut donc être copiée dans un message ou gardée en
trace sans précaution particulière (nLPD).
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.welante.columns import normalize_header, resolve_columns
from apps.welante.sources import PREFIXES_CAMPAGNE, find_sources
from apps.welante.workbook import WorkbookError, looks_like_second_header, read_workbook


class Command(BaseCommand):
    help = "Décrit la structure des exports Welante, sans afficher aucune donnée."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="data",
            help="Dossier contenant les exports (défaut : data/).",
        )

    def handle(self, *args, **options):
        dossier = Path(options["source"])
        if not dossier.exists():
            self.stderr.write(
                self.style.ERROR(
                    f"Dossier introuvable : {dossier}. Les exports se recopient à la main "
                    "sur chaque machine — ils ne transitent jamais par Git."
                )
            )
            return

        self.stdout.write(self.style.MIGRATE_HEADING(f"Exports Welante dans {dossier}/"))
        self.stdout.write("Aucune valeur n'est affichée : intitulés et agrégats seulement.\n")

        for fichier in find_sources(dossier):
            self._inspecter(fichier)

    def _inspecter(self, fichier) -> None:
        source = fichier.source
        motifs = " ou ".join(source.patterns)
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{source.label} — {motifs}"))

        if not fichier.exists:
            self.stdout.write(self.style.WARNING("  absent du dossier"))
            return

        try:
            classeur = read_workbook(
                fichier.path, header_row=source.header_row, skip_rows=source.skip_rows
            )
        except WorkbookError as exc:
            self.stderr.write(self.style.ERROR(f"  {exc}"))
            return

        self.stdout.write(f"  fichier : {fichier.path.name}")
        self.stdout.write(f"  lignes  : {classeur.row_count}")

        if source.skip_rows:
            self.stdout.write(
                f"  lecture : ligne d'en-tête {source.header_row + 1}, "
                f"ligne(s) sautée(s) {', '.join(str(n + 1) for n in source.skip_rows)}"
            )
        elif looks_like_second_header(classeur.frame):
            self.stdout.write(
                self.style.WARNING(
                    "  attention : la première ligne ressemble à un second en-tête "
                    "(déclarer skip_rows dans apps/welante/sources.py)"
                )
            )

        mapping = resolve_columns(classeur.headers, source.columns)

        self.stdout.write(f"  colonnes reconnues ({len(mapping.resolved)}) :")
        for canonique, intitule in sorted(mapping.resolved.items()):
            remplissage = self._taux_de_remplissage(classeur, intitule)
            self.stdout.write(
                f"    {canonique:<18} ← « {intitule} »   rempli à {remplissage:.0f} %"
            )

        if mapping.missing:
            style = self.style.ERROR if mapping.missing_required else self.style.WARNING
            self.stdout.write(style(f"  colonnes attendues absentes ({len(mapping.missing)}) :"))
            for colonne in mapping.missing:
                marque = "requise" if colonne.required else "facultative"
                self.stdout.write(style(f"    {colonne.name:<18} ({marque})"))

        campagnes = [
            intitule
            for intitule in mapping.unexpected
            if normalize_header(intitule).startswith(PREFIXES_CAMPAGNE)
        ]
        autres = [intitule for intitule in mapping.unexpected if intitule not in campagnes]

        if campagnes:
            self.stdout.write(
                f"  colonnes « une par saison » ({len(campagnes)}) → deviendront des campagnes :"
            )
            for intitule in campagnes:
                self.stdout.write(f"    « {intitule} »")

        if autres:
            self.stdout.write(f"  colonnes non reconnues ({len(autres)}) :")
            for intitule in autres:
                self.stdout.write(f"    « {intitule} »")

    @staticmethod
    def _taux_de_remplissage(classeur, intitule: str) -> float:
        """Proportion de cellules non vides — un agrégat, pas une donnée."""
        colonne = classeur.frame[intitule]
        remplies = sum(1 for valeur in colonne if str(valeur).strip())
        return 100 * remplies / max(len(colonne), 1)
