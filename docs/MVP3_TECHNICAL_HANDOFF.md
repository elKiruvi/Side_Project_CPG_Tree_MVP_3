# MVP 3 Technical Handoff

## 1. Purpose of this document

This is the primary continuation document for `Side_Project_CPG_Tree_MVP_3`.
It consolidates the repository audit, source-document findings, binding project
decisions, target architecture, known clinical/source ambiguities, and the
implementation sequence. A future contributor should read this document before
changing the clinical model or introducing an LLM provider.

The document deliberately distinguishes:

- **Observed fact**: verified in source code, generated artifacts, Git state, or
  the clinical PDFs.
- **Inference**: a reconstruction supported by several observations but not
  literally stated by a source.
- **Project decision**: a binding constraint for MVP 3.
- **Recommendation**: the preferred implementation direction, subject to
  evidence gathered during implementation.
- **Open clinical question**: a matter that software must not resolve without
  qualified review.

This is a research prototype. It is not a production clinical decision-support
system, does not replace clinical judgment, and must not be presented as
clinically validated merely because its software checks pass.

---

## 2. Context and objective

### 2.1 Why MVP 3 exists

Three prior implementations investigated different parts of the same problem:

1. `Side_Project_CPG_Tree_MVP` built a strong protocol-agnostic knowledge model,
   deterministic engine, provenance chain, validation layer, CLI, and static
   visualization. Its rules are mostly evaluated independently, not as one
   connected clinical flow.
2. `Side_Project_CPG_Tree_MVP_2` attempted deterministic extraction with regular
   expressions and document-specific parsers. It found many useful rules, but
   did not reliably reconstruct their global sequence or relationships.
3. `gpc-rag-chatbot` built RAG infrastructure and deterministic trees extracted
   from specific tabular patterns. Its table assumptions do not generalize to
   the two institutional protocols used here.

MVP 3 is not a mechanical merge. It uses the first repository as its software
base, selectively adapts deterministic utilities from the second, and reuses
only provider, structured-output, document-layout, and tree-navigation ideas
from the third.

### 2.2 Thesis objective

The research objective is to transform each institutional Clinical Practice
Guideline or protocol into a traceable, reviewable representation of its
clinical decision logic:

```text
condition
  -> decision
  -> action or recommendation
  -> next condition
  -> later decision or terminal outcome
```

The representation must support branches, convergences, shared actions,
exceptions, cross-references, unresolved gaps, and source conflicts. It must not
invent a relation merely to make the output look like a complete tree.

### 2.3 First functional milestone

The first MVP 3 functional milestone ends at:

```text
Candidate Graph
+ reviewable visualization
+ field-level provenance
+ Issues and conflicts
+ deterministic structural validation
```

It does **not** require a clinically approved `ApprovedKnowledgePackage`.
Clinical review of the Candidate Graph is the mechanism through which the
clinic will approve, reject, or correct the extracted structure.

### 2.4 Why visualization is critical

The clinic needs an artifact that makes the candidate logic inspectable. A
reviewer must be able to identify:

- an incorrect rule;
- an incorrect relationship;
- a missing rule or branch;
- an inaccurate transcription;
- a source conflict;
- an unsupported inference;
- a suggested correction.

The visualization is a derived review surface. It is never the canonical
clinical source of truth.

---

## 3. Audited repositories

## 3.1 `Side_Project_CPG_Tree_MVP`

### Real architecture

```text
PDF
  -> pypdf extraction, SHA-256 identity, page fragments
  -> manually engineered Python builders and YAML packages
  -> typed variables, expressions, rules, actions, provenance
  -> deterministic package validation
  -> three-valued rule engine
  -> CLI, HTML, and deterministic SVG views

reconciliation YAML
  -> typed presentation relationship inventory
  -> pathway projection and SVG
```

### Important implementation facts

- `src/cpg_tree/extraction/extractor.py` fingerprints exact PDF bytes, derives a
  content-addressed document ID, extracts every page, records extraction status,
  and emits one `SourceFragment` per page.
- `src/cpg_tree/knowledge/conditions.py` supports comparison, membership,
  boolean, temporal, `AND`, `OR`, `NOT`, and `AT_LEAST_N` expressions.
- `src/cpg_tree/knowledge/rules.py::Rule` stores condition, applicability,
  exceptions, action references, validation status, and provenance.
- A canonical `Rule` has no references to previous or next rules.
- `src/cpg_tree/engine/rules.py::evaluate_package` evaluates every rule
  independently, sorted by rule ID. Actions are declarative and do not mutate a
  case or activate a subsequent rule.
- `src/cpg_tree/reconciliation/` represents candidate relations and source
  conflicts separately from the canonical knowledge package.
- `src/cpg_tree/views/pathway.py` and `pathway_render.py` derive a visual graph
  from reconciliation artifacts. This graph is presentation, not execution.
- The current package inventory contains 42 NAC rules and 60 ITU rules.
- The audited reconciliation artifacts contain 9 NAC and 8 ITU `FLOW`
  relationships. Most rules remain disconnected, and all relationship review
  states remain proposed.

### Strengths to reuse

| Component | File or symbol | Decision |
|---|---|---|
| Content-addressed source identity | `extraction/extractor.py::fingerprint_bytes`, `document_id_from_sha256` | Reuse |
| Typed expression AST | `knowledge/conditions.py` | Reuse and extend only when justified |
| Three-valued logic | `engine/logic.py`, `engine/conditions.py` | Reuse |
| Deterministic rule evaluation | `engine/rules.py` | Reuse for approved knowledge |
| Source/provenance chain | `knowledge/documents.py`, `knowledge/provenance.py` | Adapt to field-level spans |
| Validation findings | `validation/model.py` | Reuse |
| Package checks | `validation/package_checks.py` | Adapt and expand |
| Relationship vocabulary | `reconciliation/model.py` | Adapt |
| Relationship invariants | `reconciliation/checks.py` | Adapt |
| Static provenance view | `views/provenance_view.py` | Reuse/adapt |
| Static SVG pathway | `views/pathway.py`, `views/pathway_render.py` | Adapt for Candidate Graph |
| Protocol-agnostic tests | `tests/unit/knowledge/test_third_protocol.py` and related tests | Reuse |

### Limitations to address

- There is no automatic PDF-to-rule pipeline.
- Page-level fragments are too coarse for exact citations and field-level
  provenance.
- Text extraction does not reconstruct tables, coordinates, or visual content.
- Canonical rules and canonical relations are separate and do not form one
  reviewed graph.
- The engine mechanically evaluates unresolved or unvalidated rules; consumers
  are expected to enforce safety policy.
- Variables are not traversed by the current package provenance validator.
- Actions without provenance are silently accepted.
- Python builders and committed YAML duplicate the same knowledge and create an
  authority ambiguity.
- Existing packages and relationship inventories are valuable baselines, but
  are not clinically approved ground truth.

### Components not to carry forward as final design

- A forest of independent rule cards presented as a complete clinical flow.
- Automatic promotion based solely on structural checks.
- Two competing canonical authorities for the same package.
- Generic data-science template directories that acquire no concrete role in
  the MVP 3 roadmap.

## 3.2 `Side_Project_CPG_Tree_MVP_2`

### Real architecture

```text
PDF
  -> pypdf plain/layout extraction
  -> protocol-specific regex parser
  -> Rule, Conflict, and Evidence objects
  -> deterministic structural promotion
  -> one independent decision component per FLOW rule
  -> ternary evaluation and Mermaid/ASCII presentation
```

### Important implementation facts

- `src/data/extraction.py` identifies the two protocols through hardcoded
  filename matching and emits page-level fragments.
- `src/data/parsers/nac.py` and `itu.py` are deeply tied to pages, literal
  wording, expected table layout, and known medication names.
- `src/data/parsers/common.py::compact` builds a whitespace-free view plus an
  index map into the original string. `span_compact` and
  `group_spans_compact` recover original coordinates.
- `src/model/knowledge.py` distinguishes evidence classes and relation roles,
  but clinical fields remain weakly typed.
- `src/model/validation.py::review_rules` promotes structurally valid `FLOW`
  rules to `APPROVED` automatically. This is not clinical approval.
- `src/model/tree.py::TreeBuilder` creates an independent decision root for
  each approved rule. It does not connect one clinical rule to another.
- The serialized tree omits `condition` and `action`, so semantic round-trip is
  incomplete.

### Components to reuse or adapt

| Component | File or symbol | Decision |
|---|---|---|
| Whitespace-normalized matching with source index map | `parsers/common.py::compact` | Reuse |
| Exact span recovery | `span_compact`, `group_spans_compact` | Reuse |
| Deterministic pattern detection | NAC/ITU parsers | Adapt as validators/baselines, not primary extraction |
| Conflict representation | `model/knowledge.py::Conflict` | Adapt |
| Parenthesized expression rendering | `inference/presentation.py::render_condition_structured` | Reuse/adapt |
| Existing extracted rules | generated artifacts | Review as regression corpus, not truth |
| Regex parsers | `parsers/nac.py`, `parsers/itu.py` | Review and mine for tests |

### Components to discard as MVP 3 mechanisms

- Regex as the principal interpreter of the global clinical flow.
- Automatic structural promotion to clinical approval.
- The independent-rule `TreeBuilder` as the canonical workflow.
- The current tree serialization that drops executable semantics.
- Free-text qualifiers that constrain clinical behavior but remain outside the
  executable expression.

## 3.3 `gpc-rag-chatbot`

### Real architecture

```text
PDF
  -> PyMuPDF4LLM, optional OCR, Markdown pages
  -> hierarchical chunking
  -> Ollama embeddings + Qdrant + BM25
  -> RRF + cross-encoder
  -> Ollama answer generation
  -> FastAPI and Chainlit

PDF table
  -> pdfplumber + document-specific recipe
  -> Pydantic DecisionTree JSON
  -> deterministic TreeSession wizard
```

### Important implementation facts

- `ingestion/extract.py` provides layout-aware Markdown extraction and optional
  OCR, but one sparse page triggers OCR of the complete PDF.
- `ingestion/chunking.py` recognizes Markdown headings and bold numbered
  clinical questions. It uses random UUIDs and can discard short sections.
- `trees/schema.py` demonstrates useful Pydantic discriminated unions and basic
  referential checks.
- `trees/engine.py::TreeSession` deterministically traverses a curated tree.
- `trees/table_extraction.py` supports only score-sum and major-or-N-minor table
  patterns, with recipes tied to one external NAC guideline.
- `trees/fidelity.py` uses a 60% term-overlap heuristic. This can be a warning
  signal but is not sufficient evidence verification for MVP 3.
- The RAG stack does not verify that generated citations correspond to claims.
- Agent parse failures can fail open, which is prohibited for MVP 3.

### Components to reuse or adapt

| Component | File or symbol | Decision |
|---|---|---|
| Pydantic discriminated schema pattern | `trees/schema.py` | Reuse pattern |
| Layout-aware extraction | `ingestion/extract.py` | Adapt as an additional extraction channel |
| Hierarchical section detection | `ingestion/chunking.py` | Adapt with deterministic IDs and no silent discard |
| Generic score/N-of-M builders | `trees/builders.py` | Reuse for recognized instruments |
| Table extraction | `trees/table_extraction.py` | Adapt as auxiliary evidence extraction |
| Source-only prompt constraints | `generation/prompts.py` | Adapt for extraction prompts |
| Deterministic tree navigation | `trees/engine.py` | Consider after reviewed graph projection exists |

### Components not required for the first MVP 3 milestone

- Qdrant, embeddings, hybrid retrieval, and reranking.
- LangGraph orchestration.
- RAG answer evaluation as a clinical approval gate.
- Chainlit or a complex interactive editor.
- Table recipes as a universal guideline parser.

---

## 4. Source PDFs

## 4.1 Source identity

| Protocol | Version | Pages | SHA-256 |
|---|---:|---:|---|
| CT-PL-193, community-acquired pneumonia (NAC) | 9, approved 2024-08-12 | 7 | `3a1654757801b7b618661f846f8335ced6fb9e388891d6bca96f1cd81d6f5882` |
| CT-PL-197, adult urinary tract infection and asymptomatic bacteriuria | 06, approved 2025-09-30 | 5 | `800af94bc0654138a8e213cd1e42ad2e6021a955226a142b36c5b3f24e24777a` |

Original PDFs are local immutable inputs under `data/01_raw/` and are ignored
by Git. Their hashes, filenames, page counts, and derived evidence remain
versionable.

## 4.2 CT-PL-193 NAC

### Page structure

| Page | Main content |
|---:|---|
| 1 | Objective, scope, definitions, introduction, epidemiology, etiology |
| 2 | Institutional etiology chart, manifestations, evidence grading |
| 3 | Radiography, CT, laboratory tests, cultures, sputum, FilmArray |
| 4 | FilmArray continuation, pleural fluid, hospitalization, ICU/UCE, treatment heading |
| 5 | Empiric treatment tables, antiviral content, discharge criteria |
| 6 | Education, follow-up, clinical flowchart, references |
| 7 | References, authorship, approval, change history |

### Observed clinical structure

- Compatible symptoms plus new radiographic infiltrate support the diagnosis.
- A negative initial radiograph with persistent high suspicion leads to a
  recommendation to repeat imaging in 48 hours.
- CT indications are conditional and include non-conclusive radiography,
  suspected complication, and febrile neutropenia with respiratory symptoms.
- Laboratory and microbiology requests escalate with hospitalization and
  severity.
- Hospitalization criteria combine physiologic, comorbidity, oral-tolerance,
  social, oxygen, and severity factors.
- ICU/UCE criteria include direct indications and an N-of-M criteria group.
- Treatment choices depend on care setting and resistant-organism risk.
- Culture or molecular results may modify treatment.
- Discharge, education, warning signs, and follow-up appear later.

### Reconstructed sequence

The following is a documented inference, not one literal source chain:

```text
clinical suspicion
  -> initial imaging
  -> repeat imaging or CT when indicated
  -> staged laboratory and microbiology workup
  -> hospitalization decision
  -> ICU/UCE evaluation
  -> context/risk-based treatment
  -> adjustment to results
  -> discharge and follow-up
```

### Tables, figures, and extraction limits

- Page 5 contains treatment tables with merged cells, alternatives, shared
  notes, doses, intervals, and restrictions.
- The treatment table is visually present even when a plain text extraction
  channel does not recover it correctly. This must be classified as an
  extraction limitation, not source-content absence.
- Page 6 contains a small-text clinical flowchart.
- Figure and flowchart content is pending transcription and human review.
- The canonical flow must not depend on unverified automatic transcription of
  the flowchart.

### Known ambiguities

- Narrative BUN threshold `>30` versus flowchart threshold `>20`.
- Narrative and flowchart ICU criteria differ in structure and some thresholds.
- The flowchart contains outpatient treatment details not mirrored exactly by
  the treatment table.
- Risk factors for MRSA, *P. aeruginosa*, and resistant Enterobacterales are not
  fully defined by the document.
- At least one therapeutic note is incomplete or visually ambiguous.
- Evidence grades do not accompany every recommendation.
- Prose, table, and flowchart cannot be assigned automatic precedence.

## 4.3 CT-PL-197 ITU

### Page structure

| Page | Main content |
|---:|---|
| 1 | Objective, scope, definitions, introduction |
| 2 | Epidemiology, etiology, manifestations, atypical populations, pregnancy, urinalysis |
| 3 | Gram stain, cultures, sampling, blood tests, imaging, treatment, hospitalization |
| 4 | Discharge continuation, general treatment table, pregnancy table start |
| 5 | Pregnancy table continuation, notes, authorship, change history |

### Observed clinical structure

- The document distinguishes symptoms attributable to UTI from asymptomatic
  bacteriuria.
- Diagnostic tests have different exceptions and thresholds.
- Culture thresholds depend on symptoms and sampling method.
- Blood tests, blood cultures, and imaging depend on hospitalization, severity,
  fever, shock, renal failure, persistent fever, or local complication.
- Treatment depends on lower/upper UTI, care setting, pregnancy, resistance
  risk, and shock.
- Culture-guided adjustment appears as a later action.
- Oral step-down and discharge use a shared criteria list whose global logical
  operator is not formally defined.

### Reconstructed sequence

The following is a documented inference, not one literal source chain:

```text
symptoms or asymptomatic bacteriuria
  -> lower/upper and patient-context classification
  -> diagnostic tests with exceptions
  -> sample before treatment
  -> severity-dependent blood tests or imaging
  -> inpatient or outpatient management
  -> treatment by location, pregnancy, resistance, and shock
  -> culture adjustment
  -> oral step-down or discharge
```

### Tables and extraction limits

- The general treatment table appears on page 4.
- The pregnancy table crosses pages 4 and 5 and must be treated as one logical
  source unit.
- Footnotes materially modify the meaning of rows and medications.
- Cell-to-footnote alignment requires explicit verification.

### Known ambiguities

- The document contains two non-equivalent definitions of complicated UTI.
- Upper UTI appears as a hospitalization indication while a treatment row is
  explicitly labelled outpatient upper UTI.
- Pediatric references remain despite the declared adult scope.
- Urinalysis, Gram stain, and culture exceptions are not identical.
- “Low clinical suspicion” and “correct antibiotic treatment” are not formally
  operationalized.
- Oral step-down and discharge are not separated into two explicit rule sets.
- Some pregnancy-week notes are difficult to align unambiguously with each
  preventive treatment option.

---

## 5. Binding project decisions

The following decisions are resolved and must not be reopened without an
explicit project-level decision.

### Decision 1: local environments and caches

The initial filesystem copy may contain ignored local files. In MVP 3, `.venv`,
Python bytecode, tool caches, coverage outputs, and unequivocally regenerable
temporary artifacts are removed and regenerated. Originals are never cleaned.

### Decision 2: versionable derived clinical content

The private repository may contain YAML packages, rules, technical documents,
provenance fragments, clinical review decisions, and required derived
artifacts. Original PDFs remain local and ignored.

### Decision 3: configurable reviewer policy

The number and policy of clinical reviewers are not known. The review model
must support configurable approval policy and must not hardcode one reviewer or
two independent reviewers.

### Decision 4: LLM as primary interpreter

An LLM is the principal interpretation mechanism for candidate rules and
relationships. The provider must be replaceable: GPT, DeepSeek, or another
schema-capable provider may be used. Regex and deterministic scripts remain
auxiliary preprocessing, normalization, verification, postprocessing, and
validation tools.

### Decision 5: figures and flowchart pending review

Figures and the NAC flowchart are pending transcription/review. Unverified
automatic transcription must not define canonical flow.

### Decision 6: narrative text leads flow extraction

LLM interpretation of clinical narrative, tied to source evidence, is the
primary flow source. Tables, figures, flowcharts, regex, and other modalities
may complement, contradict, or create Issues. They do not automatically
override narrative text.

### Decision 7: upper UTI conflict remains unresolved

Hospitalization for upper UTI and the outpatient upper UTI treatment row are
preserved as separate evidence. Neither interpretation wins automatically. A
source conflict Issue blocks universalizing the hospitalization statement.

### Decision 8: two complicated UTI definitions remain separate

Both definitions retain their own spans and candidate concepts/rules. They must
not be collapsed into one `itu_complicada` boolean before clinical
adjudication.

### Decision 9: textual NAC BUN candidate uses `>30`

The narrative candidate may use `BUN >30`. The flowchart observation `BUN >20`
is preserved as conflicting visual evidence and creates an Issue. The candidate
remains pending adjudication with respect to this conflict.

### Decision 10: project name versus import package

`_3` applies to the repository and distribution identity. The Python import
package remains `cpg_tree`.

### Decision 11: review decisions are versionable and append-only

Review decisions may live in the private Git repository. They should be
append-only, reference exact candidate revisions and hashes, and never silently
overwrite history.

### Decision 12: milestone ends at Candidate Graph

The first milestone produces a reviewable Candidate Graph, not a clinically
approved package. `ApprovedKnowledgePackage` compilation follows human review.

---

## 6. Target architecture

## 6.1 Pipeline

```text
PDF registered by hash
  -> multichannel extraction
  -> DocumentMap + SourceSpan inventory
  -> hierarchical segmentation
  -> LLM ObservationBatch
  -> LLM CandidateRuleBatch
  -> deterministic normalization and deduplication
  -> LLM CandidateRelationBatch
  -> global reconciliation
  -> deterministic structural validation
  -> Candidate Graph
  -> visualization + provenance + Issues
  -> clinical review
  -> ReviewDecision
  -> ApprovedRule / ApprovedRelation
  -> ApprovedKnowledgePackage
  -> deterministic engine and approved views
```

## 6.2 Architectural boundaries

- Source extraction records what was recovered and how.
- Observation extraction records source statements without declaring executable
  semantics.
- Rule extraction proposes computable semantics.
- Relationship extraction proposes topology after rule IDs exist.
- Reconciliation considers the document globally and preserves conflicts.
- Structural validation is deterministic and fail-closed.
- Clinical validation is human.
- Graph and tree views are projections from candidate or approved artifacts.
- Deterministic execution is reserved for approved knowledge or explicitly
  labelled research evaluation of candidates.

## 6.3 Provider boundary

The LLM integration should expose a small provider interface with capabilities
such as:

```text
provider identity
model identity and version/digest
structured-output capability
request timeout
retry policy
raw response capture
token/usage metadata when available
```

No provider SDK type should leak into domain models. Prompt version, schema
version, source-span IDs, request hash, raw-response hash, and parent attempt
must be recorded.

---

## 7. Recommended domain model

## 7.1 `SourceDocument`

Purpose: immutable identity and metadata for one source file.

Suggested fields:

```text
document_id
protocol_id
protocol_version
filename
sha256
media_type
byte_size
page_count
approval_date
```

## 7.2 `ExtractionRun`

Purpose: reproducible record of one multichannel extraction execution.

Suggested fields:

```text
run_id
document_id
status
started_at
completed_at
tool_versions
configuration_hash
channels
warnings
```

Statuses should include `STARTED`, `COMPLETE`, `PARTIAL`, and `FAILED`.

## 7.3 `SourceSpan`

Purpose: smallest independently citable source region.

Suggested fields:

```text
span_id
document_id
extraction_run_id
page
section_path
representation
extraction_method
extracted_text_exact
normalized_text
text_sha256
char_start
char_end
bbox
table_locator
page_image_sha256
quality_flags
```

Representations should distinguish `TEXT`, `LIST`, `TABLE`, `FOOTNOTE`,
`DIAGRAM`, `IMAGE`, and `PAGE_LAYOUT`. Quality flags should expose OCR,
uncertain reading order, table alignment uncertainty, visual-only evidence,
and cross-page continuation.

## 7.4 `Observation`

Purpose: record what was identified in the source without claiming approved
computable semantics.

Suggested fields:

```text
observation_id
kind
span_refs
exact_quote
subject_text
predicate_text
object_text
negated
generation_attempt_id
issues
```

Observation kinds may include heading, definition, recommendation, list item,
table row, table cell, footnote, explicit relation, and diagram label.

## 7.5 `VariableSpec`

Purpose: typed data referenced by clinical expressions.

Suggested fields:

```text
variable_id
label
value_type
unit
allowed_values
evidence_bindings
```

Do not collapse disputed definitions into one variable merely for convenience.

## 7.6 `ClinicalExpression`

Purpose: AST that preserves clinical logic without expanding it into a fake
sequence of graph nodes.

Atomic predicates should support typed operators such as `EQ`, `NE`, `LT`,
`LE`, `GT`, `GE`, `IN`, `NOT_IN`, `BETWEEN`, `PRESENT`, and `ABSENT`.

Logical expressions should support `AND`, `OR`, `NOT`, and `AT_LEAST_N`.
Temporal constraints should preserve amount, unit, relation, and anchor.

## 7.7 `ActionSpec`

Purpose: declarative action supported by evidence.

Suggested fields:

```text
action_id
action_type
target_text
dose_value
dose_unit
route
frequency
duration
timing
alternative_group
qualifiers
evidence_bindings
```

Alternatives share a group. They must never be converted into a medication
sequence.

## 7.8 `CandidateRule`

Purpose: versioned, non-approved computable interpretation.

Suggested fields:

```text
candidate_id
revision
protocol_version_id
observation_refs
applies_to
condition
actions
exceptions
modality
statement_kind
evidence_bindings
evidence_class
candidate_state
ambiguity_flags
generation_attempt_id
content_hash
supersedes_candidate_id
```

Candidate states may include `PROPOSED`, `BLOCKED`, `NEEDS_CHANGES`, `REJECTED`,
and `SUPERSEDED`. `APPROVED` must not be a candidate state.

## 7.9 `CandidateRelation`

Purpose: versioned, evidence-bound proposed relationship between known entity
IDs.

Suggested fields:

```text
candidate_relation_id
revision
source_ref
target_refs
relation_type
branch_label
temporal_qualifier
observation_refs
evidence_bindings
evidence_class
candidate_state
generation_attempt_id
content_hash
```

Endpoints must use typed references. Free-text pseudo IDs and wildcards are not
permitted.

## 7.10 `Issue`

Purpose: explicit ambiguity, conflict, source gap, or extraction limitation.

Suggested categories:

```text
AMBIGUITY
SOURCE_CONFLICT
MISSING_EVIDENCE
EXTRACTION_LIMITATION
SOURCE_CONTENT_ABSENT
TABLE_ALIGNMENT
NEGATION_UNCERTAIN
UNIT_UNCERTAIN
RELATION_UNCERTAIN
OUT_OF_SCOPE
```

Severity and resolution state are separate. A blocking Issue prevents
compilation but does not erase candidates or evidence.

## 7.11 `ReviewDecision`

Purpose: append-only human decision over an exact candidate revision/hash.

Suggested fields:

```text
decision_id
subject_type
candidate_id
candidate_revision
candidate_content_hash
verdict
reviewer_id
reviewed_at
rationale
checklist_answers
proposed_corrections
supersedes_decision_id
```

Verdicts may include `APPROVE`, `REJECT`, `REQUEST_CHANGES`, and `ABSTAIN`.
Approval policy must be configurable outside this entity.

## 7.12 `ApprovedRule` and `ApprovedRelation`

Purpose: immutable snapshots of exactly reviewed semantics.

Each approved artifact references:

```text
source_candidate_id
source_candidate_revision
source_candidate_hash
approval_decision_id
approved_by
approved_at
approved_content_hash
```

Corrections create a new candidate revision and new decision; they do not
silently mutate approved content.

## 7.13 `ApprovedKnowledgePackage`

Purpose: the only package intended for normal deterministic clinical-rule
execution after review.

Suggested content:

```text
schema_version
package_id
protocol and version metadata
source documents
approved variables
approved actions
approved rules
approved relations
source spans
review decisions
open accepted/non-blocking Issues
build manifest
```

## 7.14 Graph nodes are projections

Do not introduce a generic canonical `ClinicalNode` that duplicates rule,
expression, action, and terminal semantics. A graph projection may expose rule,
action, explicit terminal, and branch-context nodes, but their canonical data
remains in the typed domain entities.

---

## 8. Field-level provenance

Rule-level citations are insufficient when one rule contains several
conditions, numbers, units, actions, doses, or temporal constraints.

Each clinically meaningful claim should support a binding equivalent to:

```text
claim_path
source_span_refs
exact_quote
transformation
evidence_class
```

Example claim paths:

```text
/applies_to/operands/0
/condition/operands/1/operator
/condition/operands/1/value
/actions/0/dose_value
/actions/0/duration
/exceptions/0
/relations/0/target_ref
```

Requirements:

- `exact_quote` must be found in the referenced extraction channel, or the
  binding must reference a verified table/diagram location and reviewed manual
  transcription.
- `transformation` records normalization, abbreviation expansion, unit
  normalization, or other semantic-preserving changes.
- `evidence_class` distinguishes source-stated, extracted, normalized, inferred,
  and unresolved content.
- A model confidence score is diagnostic metadata, not evidence.
- Missing provenance is a structural failure, not a cosmetic warning.

The full audit path should be:

```text
graph element
  -> candidate rule/relation and revision
  -> field-level evidence binding
  -> observation
  -> source span
  -> page/section/bbox or offsets
  -> source document and SHA-256
```

---

## 9. State and review workflow

```text
Observation
  -> CandidateRule / CandidateRelation
  -> structurally valid Candidate Graph
  -> Clinical Review
  -> ReviewDecision
  -> ApprovedRule / ApprovedRelation
  -> ApprovedKnowledgePackage
```

Rules:

- Observations are not executable.
- Candidates are not approved knowledge.
- Candidate validation means structurally reviewable, not clinically correct.
- Rules and relations are reviewed independently.
- An approval signs one exact content hash.
- `REQUEST_CHANGES` creates a new candidate revision.
- Reviewer count and aggregation policy are configurable.
- The Candidate Graph remains valuable even when no approval has occurred.
- The clinic receives the candidate visualization, source evidence, and Issues
  as the first review artifact.

---

## 10. Graph model

## 10.1 Recommended representation

Use a:

```text
directed typed attributed multigraph
```

The semantic graph may contain convergences, disconnected components,
cross-references, and conceptual cycles. A workflow projection may require a
DAG. A tree is a review projection rooted at selected entry points, not the
canonical representation.

No graph database is required for the first milestone. Immutable Python models
plus deterministic JSON/YAML serialization are sufficient.

## 10.2 Projection node types

```text
RULE
ACTION
EXPLICIT_TERMINAL
BRANCH_CONTEXT
```

Complex conditions remain expression ASTs inside the rule. They must not be
expanded into a misleading condition sequence merely to simplify rendering.

## 10.3 Relationship semantics

| Relationship | Meaning | Clinical sequence? |
|---|---|---|
| `FLOW` | Explicit transition between concrete clinical entities | Yes |
| `BRANCH` | Explicit condition-labelled alternative | Yes |
| `REFERENCE` | Documentary/contextual reference | No |
| `SUPPORTS` | One activity informs or supports another | Not necessarily |
| `EXCEPTION_CONTEXT` | Source-declared exception without invented destination | No |
| `BRANCH_CONTEXT` | Shared context for independently conditioned alternatives | No |
| `COMPOSITION` | Logical composition such as AND/OR/N-of-M | No |
| `DECLARES_ACTION` | A rule declares an action | Internal, not next-step flow |

`GAP`, `OMITTED`, and unresolved mappings belong in the review/audit layer, not
as ordinary clinical transitions.

## 10.4 Graph constraints

- Only source-supported or explicitly human-approved relations become clinical
  `FLOW` or `BRANCH` edges.
- Inferred and unresolved relations never silently become flow.
- Alternative medications are parallel actions, not sequential edges.
- Display order is not clinical order.
- A cycle in a workflow projection is an error unless supported and explicitly
  typed as a temporal/reassessment loop.
- Disconnected components remain visible; the renderer must not manufacture
  connectors.

---

## 11. Structured LLM outputs

## 11.1 Boundary models

Use Pydantic v2 for untrusted LLM-boundary data. Initial schemas:

```text
ObservationBatch
CandidateRuleBatch
CandidateRelationBatch
```

Recommended configuration:

```python
ConfigDict(extra="forbid", frozen=True)
```

Each response envelope should contain:

```text
schema_version
run_id
segment_id
outcome
items
issues
```

Valid outcomes:

```text
COMPLETE
NO_CANDIDATES
NEEDS_MORE_CONTEXT
FAILED
```

`NO_CANDIDATES` is valid and preferable to inventing a rule.

## 11.2 Attempt record

Persist for every attempt:

```text
provider
model name and model version/digest
prompt version
schema version
temperature
seed if supported
input span IDs
input hash
raw response hash
parse result
validation errors
parent attempt ID
timing and usage metadata when available
```

## 11.3 Retry policy

Use a bounded fail-closed policy:

1. Initial strict structured-output attempt.
2. Structural retry with the same evidence and explicit parse/schema errors.
3. Retry on a smaller evidence window or split segment.
4. Quarantine after the final failure.

Never automatically repair:

- nonexistent citations;
- unknown page/span IDs;
- unsupported numbers or units;
- uncertain negation;
- doubtful footnote association;
- ambiguous clinical relationships;
- text/table/figure conflicts.

Invalid JSON, invalid schema, timeout, or provider refusal never produces a
candidate by fallback to unconstrained free text.

---

## 12. Extraction strategy

The selected strategy is:

```text
evidence
  -> observations
  -> rules
  -> relations
  -> global reconciliation
```

### Why not one prompt

`"Read this PDF and create a tree"` combines document recovery, clinical
interpretation, normalization, entity identity, relation resolution, topology,
and visualization into an opaque operation. Its errors are hard to localize and
its citations are hard to verify.

### Recommended stages

1. Register all source bytes and page counts.
2. Extract page text, layout blocks, tables, and visual-region inventory.
3. Build a hierarchical document map without dropping short or sparse content.
4. Ask the LLM for observations bounded to known spans.
5. Ask the LLM for candidate rules, without global rule-to-rule edges.
6. Normalize variables, units, duplicate actions, and candidate identity
   deterministically.
7. Ask the LLM for local relations using stable candidate IDs and original
   section context.
8. Reconcile relations globally using the complete candidate inventory,
   document outline, explicit relation observations, and Issues.
9. Validate all artifacts deterministically.
10. Render the Candidate Graph and provenance for clinical review.

### Role of deterministic logic

Regex and scripts may detect headings, lists, numeric patterns, dose formats,
temporal expressions, source overlap, and known table shapes. They may verify or
flag an LLM result. They must not be the primary mechanism that determines the
global clinical flow.

---

## 13. Validation strategy

## 13.1 Structural and automatic validation

The deterministic validator should detect at least:

- unknown schema versions;
- unknown fields;
- duplicate IDs;
- missing or malformed IDs;
- references to nonexistent entities;
- edges to nonexistent nodes;
- orphan nodes;
- unreachable nodes from declared roots;
- decisions without options;
- branches without targets;
- duplicate or overlapping branch definitions;
- self-edges and duplicate edges;
- unexpected cycles in DAG projections;
- disconnected components;
- malformed logical expressions;
- empty expression groups;
- invalid `NOT` arity;
- invalid `AT_LEAST_N` thresholds;
- variable/operator/value incompatibility;
- unsupported units;
- action fields inconsistent with action type;
- missing evidence bindings;
- nonexistent source documents, pages, spans, offsets, or bounding boxes;
- source text not found in the referenced extraction channel;
- document or span hash mismatch;
- `FLOW` relationships based only on inferred/unresolved evidence;
- decisions applied to stale candidate revisions or hashes;
- candidate-only artifacts leaking into an approved package;
- review policy configuration that cannot be satisfied.

Direct syntactic contradictions may be flagged automatically, but their
clinical resolution remains human.

## 13.2 Clinical and human validation

Clinical review must determine:

- correct comparison operator;
- correct threshold and unit;
- correct population and applicability;
- intended AND/OR/N-of-M semantics;
- scope of negation;
- exceptions and contraindications;
- temporal interpretation;
- recommendation modality;
- alternative versus combination treatment;
- table-row and footnote association;
- real clinical sequence versus textual proximity;
- precedence or coexistence of text, table, figure, and flowchart;
- completeness of the candidate flow;
- suitability of roots and terminal outcomes;
- resolution or accepted persistence of source conflicts.

A green software test suite proves technical consistency, not clinical
validity.

---

## 14. Visualization and clinical review

### Current decision

- Adapt the deterministic static HTML/SVG renderer from the base repository.
- Keep Mermaid as a secondary documentation export.
- Treat Graphviz as an optional export/layout experiment, not source of truth.
- Do not introduce a complex editor in the first implementation phase.
- Consider Cytoscape.js or React Flow only when interactive correction workflow
  requirements are concrete.

### First-milestone review view

The visualization should distinguish:

- candidate rules;
- actions;
- explicit terminals;
- `FLOW` and `BRANCH` edges;
- contextual/non-sequential relationships;
- unresolved and blocked entities;
- source conflicts;
- validation status;
- evidence class;
- source spans.

For every node or edge, the reviewer should be able to inspect:

```text
document and version
page and section
exact quote
offset/bbox or table locator
candidate revision and hash
generation attempt
structural findings
linked Issues
review history
```

Corrections should create candidate revisions and append-only review decisions.
The visualization must not directly mutate approved knowledge.

---

## 15. Incremental directory direction

The inherited repository must evolve incrementally. Do not perform a wholesale
module move before the first candidate extraction experiment establishes the
necessary interfaces.

```text
Side_Project_CPG_Tree_MVP_3/
├── data/
│   ├── 01_raw/                 # local PDFs, ignored
│   ├── 02_intermediate/        # extraction artifacts, ignored by current policy
│   └── runs/                   # future run manifests and LLM attempts
├── prompts/
│   ├── observations-v1.md
│   ├── rules-v1.md
│   └── relations-v1.md
├── protocols/
│   └── <protocol>/<version>/
│       └── approved-package.yaml
├── reviews/
│   └── <protocol>/<version>/
│       └── decisions.jsonl
├── evaluation/
│   ├── golden/
│   ├── cases/
│   └── results/
├── src/cpg_tree/
│   ├── extraction/             # expand existing package
│   ├── knowledge/              # approved canonical model
│   ├── candidates/             # future candidate contracts
│   ├── llm/                    # future provider boundary
│   ├── reconciliation/         # adapt existing relationship layer
│   ├── review/                 # future append-only workflow
│   ├── graph/                  # future graph projection
│   ├── engine/                 # preserve deterministic engine
│   ├── validation/             # expand existing checks
│   ├── views/                  # adapt deterministic visualizations
│   ├── pipelines/
│   └── cli.py
└── tests/
    ├── unit/
    ├── integration/
    ├── protocols/
    └── golden/
```

Directories should be introduced only when their first concrete artifact is
implemented.

---

## 16. Implementation plan

## Implementation Status — Phase 1 (domain contracts)

Implemented and merged via PR #3 (`feat: implement Phase 1 domain contracts`,
`c4b8521`, branch `feature/domain-contracts`). This section records what was
actually built; the plan above remains the design reference.

- **Files created:** `src/cpg_tree/candidates/` (`enums.py`, `evidence.py`,
  `hashing.py`, `observations.py`, `variables.py`, `actions.py`, `issues.py`,
  `rules.py`, `relations.py`, `expressions.py`), `src/cpg_tree/review/`
  (`model.py`, `policy.py`), `src/cpg_tree/knowledge/approved.py`,
  `src/cpg_tree/llm/schemas.py`, `src/cpg_tree/extraction/{spans,runs}.py`.
- **Files modified:** `src/cpg_tree/knowledge/{documents.py,serialization.py,
  _validation.py}` (SourceDocument registration fields, ISO datetime helper),
  `src/cpg_tree/extraction/__init__.py`, `pyproject.toml` (+pydantic).
- **Decisions:** `CandidateState` has no `APPROVED` value; content hashes are
  computed when omitted and verified when supplied (identity/lifecycle fields
  never participate); `knowledge/approved.py` is deliberately not re-exported
  from `knowledge/__init__` (import-cycle avoidance); `EvidenceClass` mirrors
  the reconciliation enum until Phase 5; the Pydantic boundary schemas are
  frozen `extra="forbid"` envelopes with a discriminated-union wire AST.
- **Quality at merge:** 970 tests, Ruff, Mypy, pre-commit, `make check` green.

## Implementation Status — Phase 2 (document extraction)

Implemented on `feature/document-extraction` (`feat(extraction): implement
structured document extraction`). This section records the actual Phase 2
architecture; the plan above remains the design reference.

### Extraction architecture actually implemented

- `extract_document_map(path, *, extracted_at=None, sparse_threshold=100)`
  in `src/cpg_tree/extraction/layout.py` produces a frozen, validated
  `DocumentMap`: `SourceDocument` + `ExtractionRun` + per-page `PageMap` +
  `SourceSpan` inventory + `ExtractionNotice` list.
- The legacy pypdf page-text path (`extract_pdf`, `ExtractionResult`,
  fragments) is preserved unchanged for compatibility; the two APIs coexist
  and serve different consumers.
- Backend: **PyMuPDF (pymupdf)** `get_text("dict")` lines (with bboxes and
  font sizes), `get_image_info`/`get_images` for figures, and
  `find_tables` for tables (strategy "lines" preferred, "text" only for
  compact bounded tables; text-strategy tables carry
  `TABLE_ALIGNMENT_UNCERTAIN`).

### Documentary element model

- `ElementKind`: TEXT, HEADING, LIST_ITEM, TABLE, TABLE_CELL, FIGURE,
  CAPTION, UNKNOWN (UNKNOWN is a fallback; the backend currently emits no
  UNKNOWN elements). Footnotes are not distinguished yet (they remain TEXT —
  limitation).
- `DocumentElement` carries element_id, page, kind, order_index, span_id,
  bbox, exact text, `section_path` (documentary heading chain, never clinical
  flow), and `parent_element_id` (cells nest under their table).
- Line granularity: these PDFs lay out each page in a single text frame, so
  lines (not blocks) are the canonical text elements.

### SourceSpan behavior

- One span per element; ids are deterministic
  (`<document_id>-p<page:03d>-e<order:03d>`) and content-addressed via the
  document; `text_sha256` is always consistent with the exact text; bboxes
  use PyMuPDF's top-left-origin, y-down, points convention.
- `char_start`/`char_end` are offsets into `PageMap.text`, which is built by
  joining text-bearing spans in element order — every text span is therefore
  an exact substring of its page text (verified by tests).
- No normalized text is produced in this phase: the canonical evidence layer
  keeps exact extracted text only.

### Sections, tables, figures

- Sections: generic heuristic (uppercase short lines, or lines whose font is
  ≥ 1.25× the page median); a heading chain is carried across pages; no
  section title is hardcoded. Heading classification is heuristic, not
  semantic.
- Tables: preserved as TABLE + TABLE_CELL elements with page, locator
  (`page N table K [cell rRcC]`), strategy provenance, and cell text; text
  inside detected tables is removed from the block inventory (no
  duplication); merged cells repeat text as reported by the backend.
  Multipage tables are never joined: a possible continuation is flagged
  (`POSSIBLE_CROSS_PAGE_TABLE` notice + `CROSS_PAGE_CONTINUATION` span flag)
  when a page ends with a table and the next page has a table near its top.
- Figures: every page image becomes a FIGURE element with bbox, `VISUAL_ONLY`
  quality flag, and the SHA-256 of the embedded image bytes when extractable;
  captions are detected as text lines directly below an image with horizontal
  overlap. Figure transcription remains pending review.

### OCR

- No OCR in this phase. Native embedded-text extraction is the only text
  channel. Figures are inventoried as visual-only evidence; nothing is
  silently OCR-mixed with native text.

### Determinism

- `run_id` and `configuration_hash` derive deterministically from the
  document id and the canonical backend configuration (backend, version,
  thresholds); timestamps are run stamps, never content identity; identical
  bytes + backend + configuration + fixed `extracted_at` ⇒ equal maps
  (tested). No random ids anywhere.

### Failures

- A file that cannot be opened raises `ValueError`; per-page failures produce
  `EXTRACTION_ERROR` pages + `PAGE_EXTRACTION_ERROR` notices (never silent
  drops); run status is `PARTIAL`/`FAILED` accordingly. Notices are technical
  (`ExtractionNotice`), deliberately separate from clinical `Issue` objects.

### Real-PDF integration results (local, not in portable CI)

- NAC (CT-PL-193 v9, `3a165475…`, `doc-3a1654757801b7b6`): 7 pages, COMPLETE,
  ~215 spans; figures on pages 1/2/6 (incl. flowchart on p6); 5 tables
  (header, etiology chart, discharge plan, references, change history); the
  "TRATAMIENTO ANTIBIÓTICO EMPÍRICO" heading is exact-quoted. The treatment
  tables described by the audit for page 5 are NOT text-recoverable (visual
  vector content without a text layer); page 5 is recorded with its
  recoverable content (discharge criteria + plan de egreso table), and this
  is a documented extraction limitation, not content absence.
- ITU (CT-PL-197 v06, `800af94b…`, `doc-800af94bc0654138`): 5 pages, COMPLETE,
  ~314 spans; figure on page 1; tables on pages 1/4/5 including the treatment
  table and the pregnancy table; the pregnancy table spanning pages 4–5 is
  preserved in parts with the `POSSIBLE_CROSS_PAGE_TABLE` notice on page 5.

### Files created / modified

- Created: `src/cpg_tree/extraction/{document.py,layout.py,serialization.py}`,
  `tests/unit/extraction/{layout_fixtures.py,test_layout.py,
  test_document_map.py}`, `tests/integration/extraction/
  test_real_document_map.py`.
- Modified: `src/cpg_tree/extraction/{__init__.py,artifacts.py}`,
  `pyproject.toml` (+pymupdf), `uv.lock`.
- Serialization: `dump_document_map`/`load_document_map` (deterministic YAML,
  round-trip tested) and `write_document_map_artifacts` for intermediate
  artifacts under `data/02_intermediate/` (gitignored; never canonical).

### New dependencies

- `pymupdf` (layout/table/image inventory). No OCR, no LLM, no RAG stack.

### Deviations from the original handoff

- `SectionHeading` was dropped from the model: heading level is derivable
  from the `section_path` chain length, and headings are ordinary elements.
- `page_image_sha256` on figure spans hashes the embedded image bytes, not a
  rendered page image (page rendering is not needed yet).
- Block-level spans were replaced by line-level spans after inspecting the
  real documents (single text frame per page).
- `pdfplumber` was not added: PyMuPDF's table evidence proved sufficient.

### Known limitations

- Text-strategy table detection is deliberately conservative; some genuine
  tables (NAC p5 treatment tables) remain as text lines or visual-only.
- Footnotes are not auto-detected; they remain TEXT elements.
- Heading classification is heuristic and can misclassify short uppercase
  lines (e.g. PMID lines).
- Bounding boxes are only as reliable as PyMuPDF's layout analysis.
- The known mypy_path latency (Phase 1) is unchanged; no repo-wide cleanup
  was performed.

### Prerequisites for Phase 3

- Segmentation over `DocumentMap.pages[*].elements` + `spans`; deterministic
  section paths already available; no further extraction work required to
  feed spans to the observation stage. The legacy `extract_pdf`/fragments
  path can remain untouched.

## Phase 0: base, security, and Git

- **Objective:** establish an independent, reproducible, private MVP 3
  repository.
- **Files/modules:** repository root, `.gitignore`, `pyproject.toml`, README,
  `AGENTS.md`, `uv.lock`, this handoff.
- **Reuse:** complete audited working tree of the predecessor, excluding `.git`.
- **Tasks:** copy and verify; clean only regenerable destination artifacts; copy
  and hash PDFs; update identity; scan secrets; run quality gates; initialize
  new Git; review staging; create private GitHub repository; verify visibility;
  push.
- **Dependencies:** rsync, Git, GitHub CLI, uv, Python 3.12.
- **Risks:** stale virtual environment, accidental PDF staging, inherited
  scheduled workflows, metadata drift.
- **Acceptance:** original repositories unchanged; no inherited `.git`; no
  secrets, PDFs, caches, or virtual environment tracked; checks recorded;
  private remote verified before push.
- **Tests/checks:** copy checksum comparison, PDF SHA-256, `git check-ignore`,
  pytest, Ruff, Mypy, pre-commit, `git diff --check`.
- **Expected result:** independent private repository ready for development.

## Phase 1: domain contracts

- **Objective:** formalize source, observation, candidate, review, and approved
  layers without replacing working engine code prematurely.
- **Files/modules:** existing `knowledge/`; new candidate/review boundary models;
  schema-version constants.
- **Reuse:** condition AST, action/rule concepts, source documents, provenance,
  validation findings.
- **Tasks:** define `SourceSpan`, observation and candidate DTOs, field-level
  evidence bindings, Issue, ReviewDecision, ApprovedRelation, package manifest,
  stable content hashing.
- **Dependencies:** Pydantic v2 for LLM boundaries; existing dataclasses may
  remain canonical for approved runtime knowledge.
- **Risks:** duplicate representations, premature universal ontology,
  incompatible serialization.
- **Acceptance:** candidates cannot be executed or marked approved; unknown
  fields fail; approval references an exact candidate hash; reviewer policy is
  configurable.
- **Tests:** schema round-trip, discriminated unions, hash determinism, stale
  review rejection, unknown-field rejection.
- **Expected result:** explicit contracts for every lifecycle layer.

## Phase 2: document extraction

- **Objective:** produce a complete multichannel source inventory with precise
  locations.
- **Files/modules:** expand `extraction/extractor.py`, `model.py`, artifacts, and
  optional layout/table adapters.
- **Reuse:** pypdf hash/page extraction; layout and OCR ideas from the chatbot;
  compact-to-original index mapping from MVP 2.
- **Tasks:** retain all pages; capture blocks and bbox; preserve exact and
  normalized text separately; inventory tables/images/diagrams; detect
  cross-page units; create deterministic spans and run manifest.
- **Dependencies:** PyMuPDF initially; pdfplumber only if its table evidence adds
  measurable value; OCR as an optional external capability.
- **Risks:** reading order, vector tables, merged cells, visual-only content,
  non-deterministic OCR.
- **Acceptance:** 7/7 NAC and 5/5 ITU pages inventoried; no silent page discard;
  page 5 NAC classified as present/visual or extraction-limited, never absent;
  ITU table continuation marked.
- **Tests:** source hashes, page counts, deterministic span IDs, valid bbox,
  exact-text lookup, repeated-run equivalence.
- **Expected result:** complete `DocumentMap` and citable `SourceSpan` inventory.

## Phase 3: segmentation and observations

- **Objective:** derive source-bound semantic observations before formal rules.
- **Files/modules:** sectioning, future `llm/schemas.py`, provider interface,
  observation prompt and run artifacts.
- **Reuse:** current uppercase heading detection, adapted hierarchical chunking,
  deterministic regex detectors as hints.
- **Tasks:** build hierarchical section paths; preserve neighboring context;
  identify lists, table rows, footnotes, definitions, recommendations, explicit
  relations, and source Issues through structured LLM output.
- **Dependencies:** selected schema-capable LLM provider adapter.
- **Risks:** splitting one recommendation, losing cross-page context, citation
  invention, discarding short but important text.
- **Acceptance:** every accepted observation points to existing spans and exact
  evidence; `NO_CANDIDATES` is supported; invalid output is quarantined.
- **Tests:** fake provider, truncated JSON, invented IDs, exact-quote failure,
  retry limit, cross-page segment fixtures.
- **Expected result:** auditable `ObservationBatch` artifacts.

## Phase 4: candidate rules

- **Objective:** formalize conditions and actions without yet inventing global
  topology.
- **Files/modules:** candidate-rule schema, normalization, variable registry,
  rule extraction prompt and pipeline stage.
- **Reuse:** existing expression AST and action vocabulary; deterministic
  normalizers and protocol baselines as tests.
- **Tasks:** extract applicability, modality, conditions, exceptions, actions,
  alternatives, temporal constraints, and evidence per field; deduplicate only
  when semantics and evidence support it.
- **Dependencies:** observations and source spans.
- **Risks:** wrong negation, threshold, unit, grouping, footnote association, or
  alternative/combination semantics.
- **Acceptance:** every clinical value/operator/action has evidence or an
  explicit unresolved Issue; no candidate has approved status.
- **Tests:** NAC BUN candidate, N-of-M ICU criteria, ITU diagnostic exceptions,
  pregnancy context, treatment alternatives, temporal requirements.
- **Expected result:** structurally valid candidate rule inventory.

## Phase 5: relations and reconciliation

- **Objective:** connect rules using source-supported local relations followed
  by global document reconciliation.
- **Files/modules:** adapt `reconciliation/`, relation prompt, graph DTOs and
  global reconciler.
- **Reuse:** current presentation roles, conflict records, and relationship
  invariants.
- **Tasks:** resolve local explicit relations with stable IDs; reconcile roots,
  transitions, branches, terminals, references, convergence, and gaps across
  sections; preserve contradictions and disconnected components.
- **Dependencies:** stable candidate rule inventory and document outline.
- **Risks:** treating proximity, a table row, repeated text, or alternatives as
  sequence.
- **Acceptance:** all endpoints resolve; inferred/unresolved evidence does not
  silently produce flow; unknown relations remain Issues; no manufactured
  connector is required for a complete-looking graph.
- **Tests:** missing endpoints, convergence, disconnected components, duplicate
  edges, contextual relationships, false medication sequence, expected roots.
- **Expected result:** source-bound Candidate Graph.

## Phase 6: automatic validation

- **Objective:** deterministically block structurally unsafe candidates and
  prepare the clinical review queue.
- **Files/modules:** expand `validation/` with source, candidate, relation,
  topology, and review-hash checks.
- **Reuse:** ValidationReport and existing package/reconciliation checks.
- **Tasks:** implement the structural checks listed in Section 13; produce
  stable finding codes and paths; define blocking versus review-only Issues.
- **Dependencies:** candidate graph and source inventory.
- **Risks:** conflating technical validity with clinical correctness; checks
  that are too permissive or reject valid ambiguity.
- **Acceptance:** no structurally invalid candidate enters the reviewable graph;
  every quarantine reason is explicit and reproducible.
- **Tests:** parameterized invalid references, malformed AST, invalid units,
  stale hashes, citation mismatch, cycles, reachability, and provenance gaps.
- **Expected result:** validated Candidate Graph plus clinical review queue.

## Phase 7: clinical review and compilation

- **Objective:** record auditable review decisions and later compile approved
  snapshots without hardcoding reviewer count.
- **Files/modules:** future `review/`, append-only decision files, policy
  configuration, approved-package compiler.
- **Reuse:** provenance/report views and validation items.
- **Tasks:** render evidence beside candidates; record approve/reject/request
  changes/abstain; create new candidate revisions for corrections; evaluate
  configured approval policy; compile only exact approved hashes.
- **Dependencies:** institutional reviewer identities and a configured policy.
- **Risks:** offline edits outside the audit trail, bulk approval, unclear
  reviewer identity, stale decisions.
- **Acceptance:** decisions are append-only; rules and relations are separate;
  a stale or insufficient set of decisions cannot compile.
- **Tests:** review history, superseded decisions, configurable one/two reviewer
  policies, incorrect-hash rejection, deterministic compilation.
- **Expected result:** review workflow and optional approved snapshots. Clinical
  approval itself is not required for the first milestone.

## Phase 8: graph, engine, and visualization

- **Objective:** produce clinic-facing candidate views and later approved
  execution without changing source semantics.
- **Files/modules:** future graph projection; adapt `views/pathway.py`,
  `pathway_render.py`, provenance and technical views; preserve `engine/`.
- **Reuse:** deterministic SVG/HTML renderer, expression rendering,
  three-valued engine, CLI discovery.
- **Tasks:** render candidate status, Issues, evidence, branch labels, actions,
  and disconnected components; export Mermaid; compile approved packages to
  the deterministic engine only after review.
- **Dependencies:** validated Candidate Graph; approved package only for normal
  execution.
- **Risks:** visual order interpreted as clinical order, hidden conflicts,
  candidate execution mistaken for approved support.
- **Acceptance:** renderer adds no edges; all visible edges trace to candidate
  relations; provenance is navigable; outputs are deterministic; candidate and
  approved modes are unmistakable.
- **Tests:** byte determinism, graph snapshots, HTML escaping, accessibility,
  links to evidence, cycle/disconnected notices.
- **Expected result:** reviewable Candidate Graph visualization and later
  approved execution path.

## Phase 9: scientific evaluation

- **Objective:** measure extraction and relation quality reproducibly.
- **Files/modules:** future `evaluation/golden/`, metrics, experiment manifests,
  result reports.
- **Reuse:** current rules and regex outputs as non-authoritative baselines;
  synthetic engine cases.
- **Tasks:** clinically adjudicate gold samples; measure candidate rule and
  relation precision/recall, field accuracy, provenance coverage, abstention,
  correction burden, and reproducibility across models/configurations.
- **Dependencies:** clinical reviewers and frozen experiment configurations.
- **Risks:** treating prior artifacts as ground truth, data leakage, changing
  model versions, optimizing only for the two documents.
- **Acceptance:** approved numeric/operator claims have 100% evidence coverage
  and zero known unsupported values; metrics include uncertainty and abstention;
  a third synthetic protocol tests generality.
- **Tests:** golden regression suite, manifest/hash checks, repeated-run
  comparison, third-protocol compatibility.
- **Expected result:** defensible thesis evidence and documented limitations.

---

## 17. Technical risks

| Risk | Severity | Required mitigation |
|---|---|---|
| Inventing rule-to-rule relationships | Critical | Separate relation phase, evidence bindings, human review |
| Treating table layout or proximity as sequence | Critical | Typed relation semantics and explicit source support |
| Losing notes, exceptions, or negation | Critical | Field-level provenance and dedicated tests |
| Automatic LLM approval | Critical | Candidate/review/approved type separation |
| Silent LLM response repair | Critical | Bounded fail-closed retry and quarantine |
| Internal PDF contradictions | High | Preserve all representations and explicit Issues |
| Reducing a graph to one tree | High | Canonical directed typed multigraph; derived tree views |
| Original PDFs committed accidentally | High | Ignore rules plus staging checks and CI guard |
| CI green while real-PDF tests skip | High | Report skips; add legal/versionable golden fixtures and skip gates |
| Visual extraction treated as verified | High | Mark visual evidence pending review |
| Provider lock-in | Medium | Provider interface and provider-neutral run metadata |
| Duplicated canonical sources | Medium | One approved package authority and generated views |
| Overdesign before first experiment | Medium | Incremental modules and smallest coherent contracts |
| Clinical data or secrets exposed | High | Private repository, secret scan, no raw PDFs, staging review |
| Non-reproducible provider/model behavior | Medium | Model version/digest, prompt/schema version, raw attempt records |

---

## 18. Known Clinical / Source Ambiguities

These are source and clinical-review Issues. Do not resolve them with external
medical knowledge.

### ITU upper infection: hospitalization versus outpatient treatment

- Evidence A lists upper UTI among hospitalization indications.
- Evidence B defines an outpatient upper UTI treatment row.
- The source does not establish whether B is an exception, simplification,
  inconsistency, or editorial error.
- Preserve both and block a universal hospitalization rule.

### Two definitions of complicated UTI

- One formulation depends on structural or functional urinary alteration.
- Another describes infection beyond the bladder and includes several clinical
  syndromes.
- Keep separate candidate definitions and evidence.
- Do not create one global `itu_complicada` boolean before adjudication.

### NAC BUN threshold

- Narrative recommendation: `BUN >30`.
- Flowchart observation: `BUN >20`.
- The narrative candidate may use `>30` but must link to a blocking or prominent
  conflict Issue until the visual discrepancy is adjudicated.

### NAC ICU criteria across modalities

- Narrative and flowchart criteria differ in grouping and thresholds.
- Preserve each representation and do not infer precedence.

### Resistant-organism risk factors

- NAC treatment branches refer to risk for MRSA, *P. aeruginosa*, or resistant
  Enterobacterales without fully defining all activation factors.
- Do not complete the definitions from external guidelines.

### Therapeutic table notes

- Some NAC notes, superscripts, dose details, or row associations are visually
  incomplete or ambiguous.
- ITU pregnancy notes span pages and merged cells.
- Table extraction must preserve uncertainty and require visual review.

### Adult scope with pediatric references

- The ITU protocol declares adult scope but retains pediatric definition or
  hospitalization language.
- Represent as out-of-scope/editorial Issue, not an adult rule.

### Diagnostic test exceptions in ITU

- Urinalysis and urine culture use different first-episode exceptions.
- Gram stain is phrased as universal in emergency care.
- Do not merge the three into one generic “perform urine tests” rule.

### Discharge and oral step-down

- The same ITU criteria are used for oral transition and/or discharge.
- The source does not state whether the two transitions are identical.

### NAC hospital and discharge list operators

- Several bullet lists appear alternative or conjunctive from context but do
  not declare a formal global operator.
- Mark the candidate operator as unresolved when the wording is insufficient.

### Source-modality precedence

- Narrative text is the primary interpretation channel by project decision.
- Tables and figures may provide evidence or conflicts.
- No modality automatically erases another source statement.

---

## 19. Immediate continuation rules

Before implementing Phase 1:

1. Create a feature branch from `main`.
2. Read this handoff and current `AGENTS.md`.
3. Inspect existing knowledge and reconciliation models before adding types.
4. Implement the smallest candidate/source contracts required by one vertical
   slice.
5. Use one representative narrative section from each PDF for the first
   provider experiment.
6. Keep provider calls behind a fakeable interface.
7. Persist raw attempt metadata without committing secrets.
8. Do not refactor the deterministic engine during candidate extraction work.
9. Do not claim clinical approval.
10. Run the full quality gate and document skipped clinical-source tests.

The recommended first vertical slice is:

```text
one source section per protocol
  -> exact SourceSpans
  -> ObservationBatch via fake and one real provider
  -> CandidateRuleBatch
  -> deterministic provenance validation
  -> static candidate review report
```

Do not begin with global graph generation or a full UI.

---

## 20. Real build state

This section is an operational record, not a future plan. It must be updated
when bootstrap commands complete.

| Field | Actual state |
|---|---|
| Build date | 2026-09-29 |
| Local path | `/home/elkiruvi/proyectos/Side_Project_CPG_Tree_MVP_3` |
| Source working tree | `Side_Project_CPG_Tree_MVP`, `feature/clinical-pathways`, `2e058896789aa3d04ebecbebf8263ed5cbe0eea7` |
| Copy verification | Initial rsync checksum comparison completed with no differences before cleanup |
| New Git branch | `main` in a new repository with no inherited history |
| Initial commit | `0de377e4e9465dc0fdeda531adc98abc9b833ffb` (`chore: bootstrap MVP 3 repository`) |
| Tests | `849 passed in 29.73s`; real-PDF integration tests ran, zero skips reported |
| Lint | `uvx ruff check --config .code_quality/ruff.toml .` passed |
| Format check | `173 files already formatted` |
| Type checks | Mypy passed with no issues in 145 source files |
| Pre-commit | All configured hooks passed on all staged files |
| NAC PDF SHA-256 | `3a1654757801b7b618661f846f8335ced6fb9e388891d6bca96f1cd81d6f5882` |
| ITU PDF SHA-256 | `800af94bc0654138a8e213cd1e42ad2e6021a955226a142b36c5b3f24e24777a` |
| PDFs tracked | No; local under `data/01_raw/` and ignored |
| Regenerated environment | Copied `.venv` was removed, then recreated with `uv sync --frozen --all-groups` from the MVP 3 lockfile |
| Removed from copied destination | Stale tool caches, Python bytecode, and coverage artifacts were removed; regenerated caches remain ignored |
| Preserved local derived data | Existing `data/02_intermediate/` and `data/08_reporting/` artifacts, ignored |
| Versioned content | 228 staged files: software, tests, YAML packages, derived reconciliation artifacts, project configuration, and documentation |
| GitHub remote | `https://github.com/elKiruvi/Side_Project_CPG_Tree_MVP_3` configured as `origin` |
| GitHub visibility | Explicitly verified as `PRIVATE` with GitHub CLI before the push attempt |
| Push state | Blocked: GitHub rejected workflow files because the active OAuth token lacks the `workflow` scope; no branch was published |
| Required user action | Run `gh auth refresh -h github.com -s workflow`, complete GitHub authorization, then run `git push -u origin main` |
| Immediate next step | Phase 1 domain contracts on a feature branch |
