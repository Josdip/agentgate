from concurrent.futures import ThreadPoolExecutor

import pytest

from agentgate.policy import ToolCall
from agentgate.store import Store


def pending(store):
    return store.submit(
        ToolCall(
            run_id="test",
            tool="refunds.create",
            arguments={"ticket_id": "T-1001", "amount_cents": 20000},
        )
    )


def test_approval_is_persistent_and_one_time(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    action = pending(store)
    assert action["result"] is None
    approved = store.review(action["id"], True)
    assert approved["outcome"] == "executed"
    assert approved["reviewer_id"] == "local-reviewer"
    with pytest.raises(ValueError):
        store.review(action["id"], True)
    assert Store(store.path).list()[0] == approved


def test_rejection_never_executes(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    assert store.review(pending(store)["id"], False)["result"] is None


def test_concurrent_reviews_execute_once(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    action = pending(store)

    def review(_):
        try:
            return store.review(action["id"], True)["outcome"]
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(review, range(2))) == ["conflict", "executed"]


def test_message_content_is_not_in_audit(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    action = store.submit(
        ToolCall(
            run_id="test",
            tool="messages.send",
            arguments={"destination": "evil", "message": "secret-value"},
        )
    )
    assert action["outcome"] == "denied"
    assert action["result"] is None
    assert "secret-value" not in str(store.list())
