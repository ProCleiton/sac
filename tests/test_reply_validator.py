import json
import tempfile
import unittest
from pathlib import Path

from sac.commands import cmd_send
from sac.config import load_config
from sac.reply_validator import ReplyValidator, SchemaError
from sac.store import Store
from sac.tmux import Tmux
from tests.test_tmux import FakeRunner

VALID = """
[session]
name = "sac-test"

[[agents]]
name = "leader"
command = "kimi"
role = "leader"

[[agents]]
name = "dev-1"
command = "opencode"
role = "aux"
"""

SCHEMA_VEREDITO = {
    "type": "object",
    "properties": {"veredito": {"enum": ["APROVADO", "REPROVADO"]}},
    "required": ["veredito"],
}


class ReplyValidatorTest(unittest.TestCase):
    def test_validate_reply_schema_ok(self):
        ok, errors = ReplyValidator.validate('{"veredito": "APROVADO"}', SCHEMA_VEREDITO)
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_validate_reply_schema_invalido(self):
        ok, errors = ReplyValidator.validate('{"veredito": "INVALIDO"}', SCHEMA_VEREDITO)
        self.assertFalse(ok)
        self.assertTrue(any("veredito" in e for e in errors),
                        "erro deve citar o campo violado")

    def test_validate_reply_schema_sem_schema(self):
        ok, errors = ReplyValidator.validate("texto livre, não JSON", None)
        self.assertTrue(ok, "sem schema, sem validação (sempre passa)")
        self.assertEqual(errors, [])

    def test_validate_reply_schema_enum(self):
        ok, errors = ReplyValidator.validate('{"veredito": "REPROVADO"}', SCHEMA_VEREDITO)
        self.assertTrue(ok)
        ok, errors = ReplyValidator.validate('{"veredito": "TALVEZ"}', SCHEMA_VEREDITO)
        self.assertFalse(ok)
        self.assertIn("APROVADO", errors[0])
        self.assertIn("REPROVADO", errors[0])
        self.assertIn("TALVEZ", errors[0])

    def test_validate_reply_schema_required(self):
        ok, errors = ReplyValidator.validate('{"outro": 1}', SCHEMA_VEREDITO)
        self.assertFalse(ok)
        self.assertTrue(any("obrigatório" in e and "veredito" in e for e in errors),
                        "erro deve indicar o campo obrigatório ausente")

    def test_validate_reply_schema_complexo(self):
        schema = {
            "type": "object",
            "properties": {
                "resumo": {"type": "string"},
                "nota": {"type": "number"},
                "detalhes": {
                    "type": "object",
                    "properties": {"arquivos": {"type": "array"}},
                    "required": ["arquivos"],
                },
            },
            "required": ["resumo", "detalhes"],
        }
        body = json.dumps({
            "resumo": "feito",
            "nota": 9.5,
            "detalhes": {"arquivos": ["a.py", "b.py"]},
        })
        ok, errors = ReplyValidator.validate(body, schema)
        self.assertTrue(ok, f"válido deve passar: {errors}")

        ok, errors = ReplyValidator.validate('{"resumo": "feito"}', schema)
        self.assertFalse(ok, "falta 'detalhes' obrigatório")

        ok, errors = ReplyValidator.validate(
            '{"resumo": "feito", "detalhes": {"arquivos": "não-é-array"}}', schema)
        self.assertFalse(ok, "tipo errado em propriedade aninhada")

    def test_validate_reply_nao_json(self):
        ok, errors = ReplyValidator.validate("pronto, sem JSON", SCHEMA_VEREDITO)
        self.assertFalse(ok)
        self.assertTrue(any("JSON" in e for e in errors))

    def test_parse_schema_invalido(self):
        with self.assertRaises(SchemaError):
            ReplyValidator.parse_schema("não-é-json")
        with self.assertRaises(SchemaError):
            ReplyValidator.parse_schema('[1, 2]')

    def test_parse_schema_fora_do_subconjunto(self):
        with self.assertRaises(SchemaError):
            ReplyValidator.parse_schema('{"oneOf": [{"type": "string"}]}')
        with self.assertRaises(SchemaError):
            ReplyValidator.parse_schema('{"type": "tipo_invalido"}')
        with self.assertRaises(SchemaError):
            ReplyValidator.parse_schema('{"type": "string", "pattern": "^a+$"}')

    def test_parse_schema_ok(self):
        schema = ReplyValidator.parse_schema(json.dumps(SCHEMA_VEREDITO))
        self.assertEqual(schema, SCHEMA_VEREDITO)


class SendComSchemaTest(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        (d / "sac.toml").write_text(VALID, encoding="utf-8")
        self.cfg = load_config(d / "sac.toml")
        self.store = Store(d / ".sac")
        self.tmux = Tmux("sac-test", runner=FakeRunner())

    def test_schema_invalido_rejeitado_no_send(self):
        with self.assertRaises(SchemaError):
            cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa",
                     schema="não-é-json")
        self.assertEqual(self.store.pending("dev-1"), [],
                         "schema mal-formado rejeita o envio")

    def test_schema_fora_do_subconjunto_rejeitado_no_send(self):
        with self.assertRaises(SchemaError):
            cmd_send(self.cfg, self.store, self.tmux, "dev-1", "tarefa",
                     schema='{"oneOf": [{"type": "string"}]}')
        self.assertEqual(self.store.pending("dev-1"), [],
                         "schema não suportado rejeita o envio")


if __name__ == "__main__":
    unittest.main()
