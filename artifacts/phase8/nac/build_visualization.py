"""Build the CT-PL-193 v9 (NAC) Phase 8A clinician visualization package.

Path configuration only; all rendering and packaging logic is generic
(``cpg_tree.views.clinical_tree`` / ``visualization_package``).
"""

from __future__ import annotations

from pathlib import Path

from cpg_tree.validation.review_packet import load_packet_graph
from cpg_tree.views.clinical_tree import load_visualization_manifest
from cpg_tree.views.markdown_tree import render_clinical_tree_markdown
from cpg_tree.views.visualization_package import write_visualization_package

ROOT = Path(__file__).resolve().parents[3]
PHASE6_DIR = ROOT / "artifacts/phase6/nac"
PHASE7_DIR = ROOT / "artifacts/phase7/nac"
PHASE8_DIR = Path(__file__).parent

_README_MD = """# Árbol clínico candidato — Neumonía adquirida en comunidad (CT-PL-193 v9)

**ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN CLÍNICA.** Generado a partir del
protocolo institucional con ayuda de inteligencia artificial. No ha sido
aprobado por personal clínico.

- Abra `clinical_tree.html` en un navegador (no requiere instalación).
- Haga clic en un recuadro para ver condición, acción, evidencia, página de
  origen e Issues. Haga clic en una flecha para ver la relación.
- `print_view.html` permite imprimir o guardar como PDF (orientación
  horizontal).
- `clinical_tree.svg` es la versión portable del árbol.
- Las cajas con borde rojo discontinuo y ⚠ están PENDIENTES DE REVISIÓN.
- Las preguntas para el revisor están en el paquete de la fase 7
  (`artifacts/phase7/nac/review_bundle/review_questions.md`).

Estado: AWAITING_CLINICAL_REVIEW · Aprobación clínica: NO.
"""

_README_TXT = """ARBOL CLINICO CANDIDATO — NAC (CT-PL-193 v9)
PENDIENTE DE VALIDACION CLINICA. No aprobado por personal clinico.

1. Abra index.html en un navegador.
2. Haga clic en cada recuadro para ver condicion, accion, evidencia e Issues.
3. Los recuadros con borde rojo discontinuo y el simbolo de advertencia
   estan PENDIENTES DE REVISION (no significa rechazado).
4. Para imprimir o guardar como PDF use la vista de impresion (print_view).
5. Para registrar correcciones use el paquete de revision de la fase 7:
   review_template.json + review_instructions.md.
"""


def main() -> None:
    graph = load_packet_graph(PHASE6_DIR / "candidate_graph.json")
    manifest = load_visualization_manifest(PHASE8_DIR / "visualization.yaml")
    (PHASE8_DIR / "clinical_tree_delivery.md").write_text(
        render_clinical_tree_markdown(graph, manifest), encoding="utf-8"
    )
    machine_manifest = write_visualization_package(
        graph=graph,
        manifest=manifest,
        out_dir=PHASE8_DIR,
        project_root=ROOT,
        phase7_review_manifest_path=PHASE7_DIR / "review_manifest.json",
        phase6_review_manifest_path=PHASE6_DIR / "review_manifest.json",
        readme_md=_README_MD,
        readme_txt=_README_TXT,
    )
    print(
        f"wrote NAC visualization: {machine_manifest['visualization_mode']}, "
        f"{len(machine_manifest['rendered_node_ids'])} nodes, "
        f"{len(machine_manifest['rendered_relation_ids'])} edges, "
        f"approval={machine_manifest['clinical_approval']}"
    )


if __name__ == "__main__":
    main()
