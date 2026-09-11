"""Self-tests for the tutor bridge.

    python platform/tests/test_bridge.py

`tools/bridge/tutor-bridge.py` is what a course page opened off disk reaches instead of
Studio. It reaches a model only through `coursekit.llm`, so nothing about wire formats is
tested here; what is its own is the key hunt, the budget per question, choosing between the
ways in and falling back from one to the other mid-question.

Every request is driven through the real `Handler` with a `BytesIO` where the socket would
be (`fakehttp.py`), and every provider is a stand-in, so no port is opened and no model is
called.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
REPO = os.path.dirname(PLATFORM)
sys.path.insert(0, PLATFORM)
sys.path.insert(0, HERE)

from coursekit.settings import SETTINGS  # noqa: E402
from fakehttp import call  # noqa: E402

BRIDGE_PATH = os.path.join(REPO, "tools", "bridge", "tutor-bridge.py")


def load_bridge():
    spec = importlib.util.spec_from_file_location("tutor_bridge_undertest", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stand_in:
    """A provider that answers however the test says, without a socket or a subprocess."""

    def __init__(self, kind="cli", label="A tool", available=True, ok=True, key=""):
        self.kind = kind
        self.label = label
        self.name = kind
        self.key = key
        self._available = available
        self._ok = ok

    def available(self):
        return self._available

    def probe(self, model="", timeout=0):
        return {"ok": self._ok, "advice": "" if self._ok else "that key was rejected"}

    def describe(self):
        return {"name": self.name, "kind": self.kind, "label": self.label}

    def with_key(self, key):
        self.key = key
        return self


class BridgeTest(unittest.TestCase):
    """One bridge per test, with its config.json in a temporary folder."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = load_bridge()

    def setUp(self):
        bridge = self.bridge
        self.tmp = tempfile.mkdtemp(prefix="bridge-test-")
        self.config = os.path.join(self.tmp, "config.json")
        for name, value in (("CONFIG_PATH", self.config), ("ECHO", False), ("FORCE_MODE", "")):
            self.addCleanup(setattr, bridge, name, getattr(bridge, name))
            setattr(bridge, name, value)
        was = dict(bridge.CFG)
        self.addCleanup(lambda: (bridge.CFG.clear(), bridge.CFG.update(was)))
        bridge.CFG.clear()
        bridge.CFG.update({"key": "", "model": SETTINGS.model_id(SETTINGS.default_model)})
        # No key of the machine's own may reach a test.
        for name in bridge.KEY_NAMES:
            if name in os.environ:
                self.addCleanup(os.environ.__setitem__, name, os.environ[name])
                del os.environ[name]

    def providers(self, cli=None, api=None):
        """Stand in for both ways to a model, and for the list `/health` reports."""
        bridge = self.bridge
        cli = cli if cli is not None else Stand_in("cli", "A tool", available=False)
        api = api if api is not None else Stand_in("anthropic", "An API", available=False)
        for name, value in (("cli_provider", lambda: cli), ("api_provider", lambda: api)):
            self.addCleanup(setattr, bridge, name, getattr(bridge, name))
            setattr(bridge, name, value)
        self.addCleanup(setattr, bridge.llm, "providers", bridge.llm.providers)
        bridge.llm.providers = lambda: [cli, api]
        return cli, api

    def answers(self, text="the answer", raises=None):
        """What `llm.complete` gives back, and what it was asked."""
        bridge = self.bridge
        seen = {}

        def complete(provider, request):
            seen["provider"], seen["request"] = provider, request
            if raises:
                raise raises
            return type("Reply", (), {"text": text})()

        self.addCleanup(setattr, bridge.llm, "complete", bridge.llm.complete)
        bridge.llm.complete = complete
        return seen

    def get(self, path):
        return call(self.bridge.Handler, "GET", path, quiet=True)

    def post(self, path, body=None):
        return call(self.bridge.Handler, "POST", path, body, quiet=True)


class TestItOnlyGoesThroughTheProviderLayer(BridgeTest):
    """One implementation of reaching a model, not two that drift (CONVENTIONS.md
    "Reaching a model")."""

    def test_no_wire_format_and_no_command_line_is_written_here(self):
        with open(BRIDGE_PATH, encoding="utf-8") as fh:
            source = fh.read()
        for gone in ("def call_api", "def call_cli", "def flatten", "def cli_argv",
                     "subprocess.run", "x-api-key"):
            self.assertNotIn(gone, source, "the bridge should not do this itself any more")

    def test_a_route_is_chosen_by_what_is_configured(self):
        self.assertIn(self.bridge.active_mode(), ("cli", "api", "none", "echo"))
        self.assertEqual(self.bridge.cli_provider().kind, "cli")
        self.assertEqual(self.bridge.api_provider().kind, "anthropic")


class TestTheBudget(BridgeTest):
    """`trim` bounds what one question costs. The prompt travels on stdin, so this is about
    money and latency rather than any command-line limit."""

    def test_the_oldest_turns_go_first(self):
        older = [{"role": "user", "content": "a" * 400},
                 {"role": "assistant", "content": "b" * 400},
                 {"role": "user", "content": "the newest question"}]
        system, kept = self.bridge.trim("s" * 100, older, 600)
        self.assertEqual(kept[-1]["content"], "the newest question")
        self.assertLess(len(kept), 3)
        self.assertLessEqual(len(system) + sum(len(m["content"]) for m in kept), 700)

    def test_the_quoted_passage_is_shortened_before_the_question_is(self):
        system, kept = self.bridge.trim("s" * 8000, [{"role": "user", "content": "why?"}], 2000)
        self.assertIn("shortened to fit", system)
        self.assertEqual(kept[0]["content"], "why?")

    def test_the_newest_message_is_clipped_only_as_a_last_resort(self):
        system, kept = self.bridge.trim("", [{"role": "user", "content": "q" * 5000}], 1000)
        self.assertEqual(system, "")
        self.assertLess(len(kept[0]["content"]), 5000)

    def test_no_budget_means_no_trimming(self):
        messages = [{"role": "user", "content": "x" * 5000}]
        system, kept = self.bridge.trim("s" * 100, messages, 0)
        self.assertEqual(len(kept[0]["content"]), 5000)

    def test_a_cli_call_is_budgeted_and_an_api_call_is_not(self):
        cli, api = self.providers(cli=Stand_in("cli"), api=Stand_in("anthropic"))
        seen = self.answers()
        self.bridge.answer("cli", cli, "s" * 99999, [{"role": "user", "content": "q"}], "", 0)
        self.assertLess(len(seen["request"].system), 99999)
        self.bridge.answer("api", api, "s" * 9000, [{"role": "user", "content": "q"}], "", 0)
        self.assertEqual(len(seen["request"].system), self.bridge.SYSTEM_CHARS)

    def test_the_token_cap_is_never_exceeded_by_what_a_page_asks_for(self):
        cli, _ = self.providers(cli=Stand_in("cli"))
        seen = self.answers()
        self.bridge.answer("cli", cli, "", [{"role": "user", "content": "q"}], "", 999999)
        self.assertEqual(seen["request"].max_tokens, self.bridge.MAX_TOKENS_CAP)


class TestTheKeyHunt(BridgeTest):
    """`candidate_keys` looks where a key of yours is already likely to be, and the source is
    always reported back."""

    def test_more_than_one_company_s_key_is_recognised(self):
        self.assertEqual(self.bridge.KEY_NAMES[0], "ANTHROPIC_API_KEY")
        self.assertIn("OPENAI_API_KEY", self.bridge.KEY_NAMES)
        self.assertTrue("sk-ant-x".startswith(self.bridge.KEY_SHAPES))

    def test_the_environment_comes_first_and_names_itself(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-from-the-environment"
        self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
        found = self.bridge.candidate_keys()
        self.assertEqual(found[0][0], "sk-ant-from-the-environment")
        self.assertIn("environment variable", found[0][1])
        self.assertEqual(self.bridge.key_source(), "ANTHROPIC_API_KEY environment variable")

    def test_the_saved_key_is_found_and_only_ever_shown_in_part(self):
        self.bridge.CFG["key"] = "sk-ant-0123456789abcdefghij"
        self.assertEqual(self.bridge.key_source(), "bridge config.json")
        hint = self.bridge.key_hint()
        self.assertNotIn("0123456789abcdef", hint)
        self.assertTrue(hint.endswith("ghij"))

    def test_a_key_too_short_to_be_one_is_said_to_be(self):
        self.bridge.CFG["key"] = "sk-ant-x"
        self.assertIn("short", self.bridge.key_hint())

    def test_nothing_that_is_not_shaped_like_a_key_is_offered(self):
        self.bridge.CFG["key"] = "hunter2"
        self.assertEqual(self.bridge.candidate_keys(), [])

    def test_the_same_key_in_two_places_is_offered_once(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-twice"
        self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
        self.bridge.CFG["key"] = "sk-ant-twice"
        self.assertEqual(len(self.bridge.candidate_keys()), 1)

    def test_a_key_is_read_out_of_an_env_file(self):
        env = os.path.join(self.tmp, ".env")
        with open(env, "w", encoding="utf-8") as fh:
            fh.write('# a comment\nOPENAI_API_KEY="sk-from-a-dotenv"\n')
        old = self.bridge.HERE
        self.bridge.HERE = self.tmp
        self.addCleanup(setattr, self.bridge, "HERE", old)
        self.assertIn(("sk-from-a-dotenv", env), self.bridge.candidate_keys())

    def test_what_is_saved_is_saved_for_next_time(self):
        self.bridge.CFG["key"] = "sk-ant-saved"
        self.assertTrue(self.bridge.save_config())
        self.bridge.CFG["key"] = ""
        self.bridge.load_config()
        self.assertEqual(self.bridge.active_key(), "sk-ant-saved")

    def test_a_config_file_that_cannot_be_read_is_not_a_crash(self):
        with open(self.config, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.bridge.load_config()
        self.assertEqual(self.bridge.active_key(), "")


class TestChoosingTheWayIn(BridgeTest):
    def test_nothing_configured_is_a_route_of_none(self):
        self.providers()
        self.assertEqual(self.bridge.active_mode(), "none")

    def test_the_api_wins_unless_the_cli_was_preferred(self):
        self.providers(cli=Stand_in("cli"), api=Stand_in("anthropic"))
        self.assertEqual(self.bridge.active_mode(), "api")
        self.bridge.CFG["prefer_cli"] = True
        self.assertEqual(self.bridge.active_mode(), "cli")

    def test_the_cli_is_used_when_there_is_no_key(self):
        self.providers(cli=Stand_in("cli"), api=Stand_in("anthropic", available=False))
        self.assertEqual(self.bridge.active_mode(), "cli")

    def test_the_environment_can_force_one_way_and_get_none_if_it_is_not_there(self):
        self.providers(cli=Stand_in("cli"), api=Stand_in("anthropic", available=False))
        self.bridge.FORCE_MODE = "api"
        self.assertEqual(self.bridge.active_mode(), "none")
        self.bridge.FORCE_MODE = "cli"
        self.assertEqual(self.bridge.active_mode(), "cli")

    def test_echo_mode_calls_nothing(self):
        self.bridge.ECHO = True
        self.assertEqual(self.bridge.active_mode(), "echo")

    def test_starting_up_prefers_the_cli_without_asking_anything(self):
        self.providers(cli=Stand_in("cli"))
        self.bridge.auto_configure()
        self.assertTrue(self.bridge.CFG["prefer_cli"])

    def test_starting_up_otherwise_takes_the_first_key_it_finds_and_says_where(self):
        self.providers()
        with open(os.path.join(self.tmp, "anthropic.key"), "w", encoding="utf-8") as fh:
            fh.write("sk-ant-on-disk\n")
        old = self.bridge.HERE
        self.bridge.HERE = self.tmp
        self.addCleanup(setattr, self.bridge, "HERE", old)
        self.bridge.auto_configure()
        self.assertEqual(self.bridge.CFG["key"], "sk-ant-on-disk")
        self.assertIn("anthropic.key", self.bridge.CFG["_found_in"])


class TestTheHttpSurface(BridgeTest):
    def test_a_page_may_call_this_from_a_file_origin(self):
        reply = call(self.bridge.Handler, "OPTIONS", "/ask", quiet=True)
        self.assertEqual(reply.status, 204)
        self.assertEqual(reply.headers.get("Access-Control-Allow-Origin"), "*")

    def test_health_says_what_can_answer_and_how(self):
        self.providers(cli=Stand_in("cli", "A tool"), api=Stand_in("anthropic", available=False))
        body = self.get("/health").json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["mode"], "cli")
        self.assertTrue(body["ready"])
        self.assertEqual([p["kind"] for p in body["providers"]], ["cli", "anthropic"])
        for older in ("cli", "model", "has_key", "key_source"):
            self.assertIn(older, body, "a page built before `providers` looks for this")

    def test_an_unknown_path_says_what_this_bridge_serves(self):
        self.assertEqual(self.get("/whatever").status, 404)
        self.assertIn("/ask", self.post("/whatever").error)

    def test_a_body_that_is_not_json_is_a_400(self):
        reply = call(self.bridge.Handler, "POST", "/ask", raw_body=b"<html>", quiet=True)
        self.assertEqual(reply.status, 400)
        self.assertIn("request body", reply.error)


class TestConfigure(BridgeTest):
    def test_a_key_is_stored_and_the_cli_preference_dropped(self):
        self.providers(api=Stand_in("anthropic"))
        self.bridge.CFG["prefer_cli"] = True
        body = self.post("/configure", {"key": "sk-ant-typed-in"}).json()
        self.assertTrue(body["has_key"])
        self.assertFalse(self.bridge.CFG["prefer_cli"])
        with open(self.config, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["key"], "sk-ant-typed-in")

    def test_choosing_the_cli_clears_the_key(self):
        self.providers(cli=Stand_in("cli"))
        self.bridge.CFG["key"] = "sk-ant-old"
        body = self.post("/configure", {"use_cli": True}).json()
        self.assertFalse(body["has_key"])
        self.assertEqual(body["mode"], "cli")

    def test_only_a_model_on_the_list_is_taken(self):
        self.providers()
        real = self.bridge.SETTINGS.models[0]["id"]
        self.post("/configure", {"model": real})
        self.assertEqual(self.bridge.CFG["model"], real)
        self.post("/configure", {"model": "a-model-nobody-offers"})
        self.assertEqual(self.bridge.CFG["model"], real)


class TestConnect(BridgeTest):
    """Find a working route without asking the user for anything."""

    def test_a_signed_in_cli_wins_and_no_key_is_asked_for(self):
        self.providers(cli=Stand_in("cli", "A tool"))
        body = self.post("/connect", {}).json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["mode"], "cli")
        self.assertIn("No API key needed", body["note"])
        self.assertTrue(self.bridge.CFG["prefer_cli"])

    def test_a_cli_that_is_installed_but_signed_out_is_reported_and_passed_over(self):
        self.providers(cli=Stand_in("cli", "A tool", ok=False), api=Stand_in("anthropic"))
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-works"
        self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
        body = self.post("/connect", {}).json()
        self.assertFalse(body["steps"][0]["ok"])
        self.assertTrue(body["ok"])
        self.assertEqual(body["mode"], "api")

    def test_a_key_that_works_is_saved_unless_it_came_from_the_environment(self):
        self.providers(api=Stand_in("anthropic"))
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-from-env"
        self.addCleanup(os.environ.pop, "ANTHROPIC_API_KEY", None)
        self.post("/connect", {})
        self.assertEqual(self.bridge.CFG["key"], "", "the environment is not copied to disk")

    def test_a_dead_key_stops_poisoning_every_request(self):
        self.providers(api=Stand_in("anthropic", ok=False))
        self.bridge.CFG["key"] = "sk-ant-rejected"
        body = self.post("/connect", {}).json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["need"], "key")
        self.assertEqual(self.bridge.CFG["key"], "")
        self.assertIn("removing the rejected key", body["steps"][-1]["tried"])


class TestTestKey(BridgeTest):
    def test_with_no_key_there_is_nothing_to_test(self):
        self.providers()
        body = self.post("/testkey", {}).json()
        self.assertFalse(body["ok"])
        self.assertIn("No key", body["reason"])

    def test_a_rejected_key_comes_back_with_the_raw_reason(self):
        self.providers(api=Stand_in("anthropic", ok=False))
        self.bridge.CFG["key"] = "sk-ant-rejected"
        body = self.post("/testkey", {}).json()
        self.assertFalse(body["ok"])
        self.assertIn("rejected", body["reason"])

    def test_a_key_that_works_says_so(self):
        self.providers(api=Stand_in("anthropic"))
        self.bridge.CFG["key"] = "sk-ant-fine"
        self.assertTrue(self.post("/testkey", {}).json()["ok"])


class TestAsk(BridgeTest):
    def test_a_question_with_no_messages_is_refused(self):
        self.assertEqual(self.post("/ask", {"messages": []}).status, 400)

    def test_echo_mode_answers_without_calling_anything(self):
        self.bridge.ECHO = True
        body = self.post("/ask", {"messages": [{"role": "user", "content": "hello"}]}).json()
        self.assertEqual(body, {"text": "ECHO: hello", "mode": "echo"})

    def test_with_no_way_to_a_model_the_page_is_told_what_to_do(self):
        self.providers()
        reply = self.post("/ask", {"messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(reply.status, 400)
        self.assertIn("API key", reply.error)

    def test_an_answer_carries_the_route_it_came_through(self):
        self.providers(cli=Stand_in("cli"))
        self.answers("42")
        body = self.post("/ask", {"system": "s", "messages": [{"role": "user", "content": "q"}]}).json()
        self.assertEqual(body, {"text": "42", "mode": "cli"})

    def test_a_key_sent_by_the_page_is_only_a_fallback(self):
        """A stale value in a browser must never override what was configured here."""
        self.providers(api=Stand_in("anthropic"))
        self.bridge.CFG["key"] = "sk-ant-configured"
        self.answers()
        self.post("/ask", {"key": "sk-ant-from-the-page",
                           "messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(self.bridge.CFG["key"], "sk-ant-configured")

    def test_a_page_key_is_taken_when_there_is_none_here(self):
        self.providers(api=Stand_in("anthropic"))
        self.answers()
        self.post("/ask", {"key": "sk-ant-from-the-page",
                           "messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(self.bridge.CFG["key"], "sk-ant-from-the-page")

    def test_the_failure_kind_travels_so_the_page_can_decide_what_to_offer(self):
        self.providers(cli=Stand_in("cli"))
        self.answers(raises=self.bridge.LLMFailed("out until 3pm.", kind="quota",
                                                  detail="usage limit", resets_at="3pm"))
        reply = self.post("/ask", {"messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(reply.status, 502)
        self.assertEqual(reply.json()["why"], "quota")
        self.assertEqual(reply.json()["resetsAt"], "3pm")

    def test_a_timeout_is_a_504(self):
        self.providers(cli=Stand_in("cli"))
        self.answers(raises=self.bridge.LLMFailed("took too long", kind="timeout"))
        self.assertEqual(self.post("/ask", {"messages": [{"role": "user", "content": "q"}]}).status,
                         504)

    def test_anything_else_still_owes_the_page_an_answer(self):
        self.providers(cli=Stand_in("cli"))
        self.answers(raises=RuntimeError("something nobody classified"))
        reply = self.post("/ask", {"messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(reply.status, 502)
        self.assertEqual(reply.json()["why"], self.bridge.UNKNOWN)


class TestFallingBackMidQuestion(BridgeTest):
    """The live route said no. When the other one is configured, use it and say so."""

    def _one_provider_fails(self, kind):
        cli, api = self.providers(cli=Stand_in("cli"), api=Stand_in("anthropic"))
        failure = self.bridge.LLMFailed("no", kind=kind)
        calls = []

        def complete(provider, request):
            calls.append(provider)
            if len(calls) == 1:
                raise failure
            return type("Reply", (), {"text": "the other one answered"})()

        self.addCleanup(setattr, self.bridge.llm, "complete", self.bridge.llm.complete)
        self.bridge.llm.complete = complete
        return calls

    def test_a_cli_that_cannot_answer_hands_over_to_the_key(self):
        self.bridge.CFG["prefer_cli"] = True
        self._one_provider_fails("transient")
        body = self.post("/ask", {"messages": [{"role": "user", "content": "q"}]}).json()
        self.assertEqual(body["text"], "the other one answered")
        self.assertEqual(body["mode"], "api")
        self.assertIn("command-line tool could not answer", body["notice"])

    def test_a_rejected_key_hands_over_to_the_cli(self):
        self._one_provider_fails("auth")
        body = self.post("/ask", {"messages": [{"role": "user", "content": "q"}]}).json()
        self.assertEqual(body["mode"], "cli")
        self.assertIn("rejected", body["notice"])

    def test_a_timeout_on_the_cli_is_not_worth_trying_again_elsewhere(self):
        """Every model on the chain draws on the same account, and a slow answer is not the
        other route's to give."""
        self.bridge.CFG["prefer_cli"] = True
        calls = self._one_provider_fails("timeout")
        self.assertEqual(self.post("/ask", {"messages": [{"role": "user", "content": "q"}]}).status,
                         504)
        self.assertEqual(len(calls), 1)

    def test_the_first_failure_is_the_one_reported_when_both_fail(self):
        self.providers(cli=Stand_in("cli"), api=Stand_in("anthropic"))
        self.bridge.CFG["prefer_cli"] = True
        self.answers(raises=self.bridge.LLMFailed("the first one", kind="transient"))
        reply = self.post("/ask", {"messages": [{"role": "user", "content": "q"}]})
        self.assertEqual(reply.status, 502)
        self.assertEqual(reply.error, "the first one")


if __name__ == "__main__":
    unittest.main(verbosity=2)
