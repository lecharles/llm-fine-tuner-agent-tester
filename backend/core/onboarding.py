"""S71: first-run onboarding — a 10-pair starter demo dataset, seeded once.

The gap this closes: a brand-new account (signup on the VPS, or the local
user auto-provisioned by `llmtuner up` on a Mac) landed on an empty Datasets
page with no data and no keys, so the first loop (dataset -> train ->
compare) could not even be demonstrated without first generating pairs. The
Welcome page's "Start tuning" CTA promised a journey the account had nothing
to start.

Fix: every human-shaped account gets one tiny, self-contained demo dataset on
creation — 10 Q&A pairs about a sample refund policy (the same 30-day/receipt
storyline docs/DEMO.md and docs/QUICKSTART.md tell), so a fresh account can
hit Train immediately. The pairs carry the H4 iters guidance in the dataset
description (10-20 smoke, 200-400 real tune) so the quickstart advice lives
where the new user actually looks.

Design rules honored:
- IDEMPOTENT: keyed on `source == DEMO_SOURCE` per user; calling the seed any
  number of times yields at most one demo dataset. Deleting it and asking for
  it again via POST /api/datasets/seed-demo re-creates it — the endpoint is
  the deliberate user-facing "bring it back" path, the auto-seed is the
  silent first-run path.
- NEVER BREAKS SIGNUP: the auto-seed is best-effort; any failure rolls the
  seed back and is logged, the user is still created (their signup already
  committed — the demo rides on a later, separate commit).
- NO SEEDING SERVICE LANES: `ensure_lane_user` stays untouched on purpose.
  A tmux lane's shared identity is an API surface, not a person to onboard;
  its dataset list must stay clean for automation.

No migration needed: `datasets` and `qa_pairs` already exist; nothing new is
stored, the demo is ordinary rows a user can edit/delete/share like any other.
"""

import logging

from sqlalchemy.orm import Session

from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User

logger = logging.getLogger("llmtuner.onboarding")

# The marker that makes the demo findable (and idempotent) without a schema
# change: a private dataset whose source is "seed". The frontend badges it.
DEMO_SOURCE = "seed"
DEMO_NAME = "Starter demo: refunds"
DEMO_DESCRIPTION = (
    "A 10-pair demo dataset seeded on signup so you can train immediately: "
    "a sample refund policy (30-day window, receipt required). Edit it, "
    "replace it, or delete it once your own data is in. Recommended first "
    "run: 10-20 iters to smoke-test the pipeline, then 200-400 iters for a "
    "model worth keeping (see docs/QUICKSTART.md)."
)
DEMO_USE_CASE_PROMPT = (
    "A customer support expert that answers questions about our refund "
    "policy: 30-day window, receipt required."
)

# Ten pairs, same storyline as docs/DEMO.md's demo-refunds.csv (extended).
DEMO_PAIRS: list[tuple[str, str]] = [
    (
        "What is the refund window for a standard purchase?",
        "Standard purchases can be refunded within 30 days of purchase when "
        "you present the receipt.",
    ),
    (
        "Can I return an item without a receipt?",
        "Without a receipt we cannot issue a cash refund; the item may be "
        "exchanged or returned for store credit at a manager's discretion.",
    ),
    (
        "Can I return this without a receipt after 40 days?",
        "No. The refund window is 30 days and a receipt is required, so a "
        "40-day no-receipt return is outside the policy on both counts.",
    ),
    (
        "How quickly will my refund appear on my card?",
        "Card refunds post within 3-5 business days after the return is "
        "processed in-store or received at our returns center.",
    ),
    (
        "Do refunds go back to the original payment method?",
        "Yes. Refunds are always issued to the original payment method shown "
        "on the receipt; store credit is the only alternative, for "
        "receipt-less returns.",
    ),
    (
        "Can I exchange an item instead of getting a refund?",
        "Yes, exchanges are free within the same 30-day window with the "
        "receipt, and the exchange does not restart the refund clock.",
    ),
    (
        "What is the policy for defective items?",
        "Defective items are refunded or replaced even after 30 days, within "
        "90 days of purchase, with proof of purchase if possible.",
    ),
    (
        "Are sale or final-sale items refundable?",
        "Sale items follow the same 30-day rule with a receipt; items marked "
        "FINAL SALE are not refundable and not exchangeable.",
    ),
    (
        "How do I return an online order?",
        "Start a return from your order page to get a prepaid label, pack the "
        "item with the order confirmation as your receipt, and ship it within "
        "30 days of delivery.",
    ),
    (
        "Is there anything that can never be refunded?",
        "Final-sale items, opened hygiene products, and gift cards are never "
        "refundable; everything else follows the 30-day receipt rule.",
    ),
]


def get_existing_demo(db: Session, user: User) -> Dataset | None:
    """The user's seeded demo, if it exists (idempotency probe)."""
    return (
        db.query(Dataset)
        .filter(Dataset.user_id == user.id, Dataset.source == DEMO_SOURCE)
        .first()
    )


def build_demo_dataset(db: Session, user: User) -> Dataset:
    """Create the demo dataset + 10 pairs on `db` WITHOUT committing.

    The caller owns the transaction (signup commits the user separately; the
    endpoint commits here). Flushes to give the FK real dataset ids.
    """
    dataset = Dataset(
        user_id=user.id,
        name=DEMO_NAME,
        description=DEMO_DESCRIPTION,
        source=DEMO_SOURCE,
        use_case_prompt=DEMO_USE_CASE_PROMPT,
        visibility="private",
    )
    db.add(dataset)
    db.flush()
    for question, answer in DEMO_PAIRS:
        db.add(
            QAPair(dataset_id=dataset.id, question=question, answer=answer)
        )
    db.flush()
    return dataset


def seed_demo_dataset(db: Session, user: User) -> tuple[Dataset, bool]:
    """Idempotent seed. Returns (dataset, created) — created=False means the
    user already had their demo and nothing was written."""
    existing = get_existing_demo(db, user)
    if existing is not None:
        return existing, False
    dataset = build_demo_dataset(db, user)
    return dataset, True


def best_effort_seed(db: Session, user: User) -> None:
    """Auto-seed hook used by signup and local-user provisioning.

    Never raises: a broken onboarding demo must not cost a user their
    account. The user row is already committed by the time this runs, so the
    rollback here only unwinds the seed itself.
    """
    try:
        _, created = seed_demo_dataset(db, user)
        if created:
            db.commit()
    except Exception:  # noqa: BLE001 - onboarding is strictly best-effort
        logger.exception("S71 demo seed failed for user %s (signup unaffected)", user.id)
        db.rollback()
