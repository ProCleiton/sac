import unittest

from sac.config import ConfigError
from sac.layout import Col, Leaf, Row, SplitOp, build_plan, parse_spec


class ParseSpecTest(unittest.TestCase):
    def test_folha_unica(self):
        self.assertEqual(parse_spec("leader"), Leaf("leader"))

    def test_empilhado(self):
        self.assertEqual(parse_spec("dev-1,auditor"),
                         Row([Leaf("dev-1"), Leaf("auditor")]))

    def test_colunas(self):
        self.assertEqual(parse_spec("dev-1;auditor"),
                         Col([Leaf("dev-1"), Leaf("auditor")]))

    def test_precedencia_virgula_sobre_ponto_e_virgula(self):
        self.assertEqual(
            parse_spec("dev-1,auditor;info"),
            Col([Row([Leaf("dev-1"), Leaf("auditor")]), Leaf("info")]))

    def test_espacos_tolerados(self):
        self.assertEqual(parse_spec(" dev-1 , auditor "),
                         Row([Leaf("dev-1"), Leaf("auditor")]))

    def test_invalidos(self):
        for spec in ("", "dev-1,,auditor", "dev-1;", ";dev-1", ","):
            with self.assertRaises(ConfigError, msg=f"spec {spec!r} deve falhar"):
                parse_spec(spec)


class BuildPlanTest(unittest.TestCase):
    def test_folha_unica(self):
        plan = build_plan({"main": "leader"})
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].name, "main")
        self.assertEqual(plan[0].ops, [SplitOp("leader", "area", 85)])

    def test_empilhado_50_50(self):
        plan = build_plan({"trabalho": "dev-1,auditor"})
        self.assertEqual(plan[0].ops, [SplitOp("dev-1", "area", 85),
                                       SplitOp("auditor", "row", 50)])

    def test_colunas_desbalanceadas(self):
        plan = build_plan({"trabalho": "dev-1,auditor;info"})
        self.assertEqual(plan[0].ops, [SplitOp("dev-1", "area", 85),
                                       SplitOp("auditor", "row", 50),
                                       SplitOp("info", "col", 33)])

    def test_ordem_das_windows_preservada(self):
        plan = build_plan({"main": "leader", "trabalho": "dev-1"})
        self.assertEqual([w.name for w in plan], ["main", "trabalho"])


if __name__ == "__main__":
    unittest.main()
