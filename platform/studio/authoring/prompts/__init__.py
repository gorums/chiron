"""The prompts Studio sends, one module per stage.

These are the machine-driven twin of `common/skills/course-author/`. The skill guides a
model that can read files and iterate; these run unattended, so they carry their contract
inline and state the output format exactly. When the module format or a JSON schema changes,
both have to change - the skill's `references/` remain the human-readable source of truth.

They were one file, so that the whole voice of a generated course could be read in one
sitting. At eight hundred lines that stopped being true, and the thing worth reading in one
sitting turned out to be `common.py`: the house style every stage prepends, and the context
every stage gives the model. The rest is one module per stage of a run.

    common        VOICE, and where in the course this module sits
    curriculum    the plan, proposed before a course exists
    modules       one module's text: written, or patched in place
    assessments   its quiz, flashcards and suggested questions
    library       glossary, mental models, resources, worksheets, plan pages
    media         figures and notebooks, in a delimited format rather than JSON
    reviews       reading a finished module critically

A file is named for the stage in the plural and the function it holds in the singular
(`modules.module`, `reviews.review`), so a submodule never shadows a re-exported name.

Every name is re-exported here, so a caller still writes `prompts.module(...)` and does not
have to know which file a stage lives in.
"""

from __future__ import annotations

from .assessments import (ASSESS_SCHEMA, assessment, patch_assessment,  # noqa: F401
                         suggestions)
from .common import VOICE, course_context  # noqa: F401
from .curriculum import PLAN_SCHEMA, plan  # noqa: F401
from .library import (WORKSHEET_PLAN_SCHEMA, glossary, mental_models, plan_docs,  # noqa: F401
                      resources, worksheet, worksheet_plan)
from .media import FIGURES_FORMAT, NOTEBOOKS_FORMAT, figures, notebooks  # noqa: F401
from .modules import (MODULE_SPEC_SCHEMA, direction, module, module_first,  # noqa: F401
                     module_spec, patch_module)
from .reviews import REVIEW_SCHEMA, quiz_listing, review  # noqa: F401
