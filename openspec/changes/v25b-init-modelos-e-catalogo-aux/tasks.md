# Tasks — v25b-init-modelos-e-catalogo-aux

## 1. Sugestão de modelos por harness
- [x] 1.1 Testes: kimi → aliases das tabelas `[models."*"]` do config do kimi
      (tomllib mockado/arquivo em tmp); ausente/inválido → lista vazia
- [x] 1.2 Testes: opencode → parse da saída de `opencode models` (subprocess
      mockado); timeout/erro → lista vazia
- [x] 1.3 Testes: wizard com lista → resposta por número seleciona o modelo;
      Enter = vazio (sem `--model`); número inválido repete a pergunta
- [x] 1.4 Testes: wizard sem lista (harness desconhecido/falha) → pergunta de
      texto livre atual
- [x] 1.5 Implementar `_list_models()` + integração na pergunta de modelo

## 2. Catálogo aux sem líder
- [x] 2.1 Testes: catálogo dos agentes 2+ NÃO contém líder/orquestrador; default
      é desenvolvedor; agente 1 continua recebendo líder sem pergunta
- [x] 2.2 Implementar filtro no `_ask_contract()`

## 3. Fechamento
- [x] 3.1 Suíte 100% verde
- [x] 3.2 `openspec validate v25b-init-modelos-e-catalogo-aux` válido
- [x] 3.3 Validação ao vivo em diretório descartável (init com lista de modelos)
