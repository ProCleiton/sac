## Context

SAC v1.5 está em andamento (change v15-ux-boot-e-init, working tree). Durante o
uso ao vivo da esteira CCB em 24/07, 4 bugs de confiabilidade de mensageria
foram observados com evidência direta — todos em produção (sessão real, agentes
reais). A v1.6 endereça os 4 bugs sem introduzir novas capacidades.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0 (testes com pytest). Suíte: ~167 passed.

## Goals / Non-Goals

**Goals:**
- Reply sempre entregue ao leader (eliminar perda silenciosa)
- `sac done` sempre limpa claimed com verificação atômica (0 ocorrências futuras)
- Raiz da fila determinística via SAC_ROOT (evitar ambiguidade multi-.sac)
- Poke sempre acorda o agente (Enter + delay + hint textual)

**Non-Goals:**
- Não alterar o formato do arquivo .msg (cabeçalhos existentes inalterados)
- Não adicionar novos comandos (apenas flags/env)
- Não refatorar a Store inteira — apenas finish() e init
- Não mexer no fluxo de reply_to da v1.4 (continuam funcionando)

## Decisions

### D1. deliver_reply com verificação + fallback

**Problema observado**: agente envia `sac send leader "resultado"`, comando
retorna "mensagem enviada ✅", mas o leader nunca vê a reply. Três ocorrências
em 24/07. Remédio: `sac inject leader` destrava.

**Raiz provável**: o daemon tenta deliver_reply, mas (a) o leader pode não ter
pane ativo (janela fechada), (b) o daemon treat a reply como tarefa normal e
não faz o fura-fila, ou (c) o `cfg.agent(to)` falha silenciosamente.

- **Escolha**: `daemon._process_agent()` verifica `cfg.agent(to)` com try/except
  antes de tentar deliver. Se o destino não é agente conhecido, registra
  `loop_error` e pula (não perde a mensagem — fica na inbox). O daemon também
  verifica se o pane do destino existe via `find_pane_id()` — se não existe,
  loga aviso e mantém na inbox (será entregue quando o pane subir).
- **Fallback no send**: quando `sac send` detecta que o daemon não está ativo,
  o poke manual inclui Enter + hint textual (ver D4). Isso garante que mesmo
  sem daemon, a mensagem cutuca o agente.
- **Por que não apenas aumentar frequência do daemon?**: o problema não é
  latência — é a entrega nunca acontecer. Frequência não corrige perda.
- **Teste de regressão**: mockar `find_pane_id` retornando None →
  deliver_reply deve logar aviso e não perder a mensagem.

### D2. done com atomicidade (write-ahead + fsync + verificação)

**Problema observado (CRÍTICO, 3 ocorrências)**: o agente executa `sac done <id>
"resumo"`, vê "concluída ✅", mas o arquivo .msg permanece em claimed e o evento
done não aparece no log.jsonl. A fila do agente trava — a próxima mensagem não
é entregue porque o claimed não está vazio.

**Raiz**: `Store.finish()` move o arquivo (claimed→done) e DEPOIS tenta escrever
o log. Se o log falha (IOError, permissão, filesystem cheio), o arquivo já foi
movido — o log fica sem o evento done, e se o processo morre entre o move e o
log, o claimed fica vazio mas o log não registra. Pior: em alguns casos o move
falha silenciosamente (ex.: permissão negada no destino, src em device diferente
com `shutil.move` que copia+apaga e a apaga falha), o arquivo permanece em
claimed, mas o código imprime "concluída ✅" porque o método não retornou erro.

- **Escolha**: inverter a ordem — escrever o log PRIMEIRO (write-ahead), fsync
  no diretório do log, e SÓ ENTÃO mover o arquivo. Após o move, verificar que
  o arquivo NÃO existe mais em claimed. Se o move falhou, logar `loop_error`
  com detalhes e IMPRIMIR erro em vez de "concluída ✅".
- **Implementação**:
  1. Serializar evento done como dict JSON.
  2. Abrir `log.jsonl` em modo append, escrever linha.
  3. `file.flush()` + `os.fsync(file.fileno())`.
  4. Fechar arquivo.
  5. `shutil.move(src, dst)`.
  6. Verificar `not src.exists()`.
  7. Se existe: logar `loop_error("finish_move_failed", src)`, imprimir erro.
  8. Se não existe: imprimir "concluída ✅" + resumo.
- **Por que não usar rename atômico?**: `os.rename()` não funciona entre
  dispositivos diferentes (cross-filesystem). `shutil.move` com fallback de
  cópia+apaga é o comportamento correto para o caso geral. A verificação
  pós-move cobre a falha de apaga.
- **Teste de regressão**: mockar `shutil.move` para lançar `OSError` →
  finish() deve logar `loop_error` e NÃO imprimir "concluída".
- **Lições da v1.4**: o gate da v1.4 validou o reply marking estaticamente,
  mas o bug real (done sem atomicidade) só apareceu ao vivo. Esta change
  inclui TDD + teste real ao vivo antes do commit (lição registrada).

### D3. SAC_ROOT explícito

**Problema observado**: agente com cwd `/home/dev/Github` (raiz do workspace)
acabou usando `/home/dev/Github/sac/.sac` porque o cwd dele era o diretório do
repo SAC (sessão antiga tinha `.sac/` lá). A descoberta automática por cwd é
ambígua quando existem múltiplos `.sac/` na árvore de diretórios.

- **Escolha**: três formas de definir a raiz, com precedência clara:
  1. CLI `--sac-root <path>` (máxima precedência)
  2. env `SAC_ROOT=<path>`
  3. Config `[session] root = "<path>"` no `sac.toml`
  4. Fallback: `Path.cwd() / ".sac"` (comportamento atual)
- **Implementação**:
  - `Config.session.root: str | None = None` (campo novo).
  - `Store.__init__(root: Path | None = None)` — se root=None, usa descoberta.
  - `resolve_root()`: CLI > env > config > cwd.
  - A CLI passa `--sac-root` para `Store.__init__`.
- **Validação**: se root é relativo, rejeitar com erro. Apenas caminhos
  absolutos são aceitos para evitar ambiguidade.
- **Por que não apenas documentar "use diretório X"?**: documentação não
  impede o erro. A raiz explícita é enforce pelo código.
- **Compatibilidade**: config sem root + sem env + sem --sac-root = cwd
  (comportamento idêntico ao atual). Zero breaking change.
- **Teste de regressão**: `Store(root=Path("/tmp/test-sac"))` → caminhos
  resolvem para `/tmp/test-sac/.sac/inbox/...`; `Store(root=None)` →
  resolve para `Path.cwd() / ".sac"`.

### D4. Poke com Enter forçado + delay + hint

**Problema observado (múltiplas ocorrências)**: mensagem nova fica na inbox,
o daemon poke cutuca o pane com `"SAC: ..."`, mas o agente não reage — o texto
aparece no terminal mas o harness não processa como comando. Remédio: `sac
inject <agente>` re-injeta o prompt completo e destrava.

**Raiz**: o daemon injeta o corpo da mensagem com `send-keys -l` (literal) e um
Enter. Em alguns estados do harness (especialmente opencode), o Enter simples
não é suficiente — o harness está esperando entrada diferente, ou o texto colado
não termina com newline que o harness reconhece.

- **Escolha**:
  1. Delay de 0.2s entre o texto e o Enter (via `time.sleep(0.2)`).
  2. Dois Envios separados: `send-keys -l -- <body>` e `send-keys Enter`.
  3. Hint textual adicional ao final: `"SAC: mensagem — rode \`sac next\`"`.
- **Motivo**: o delay dá tempo para o harness processar o texto antes do Enter.
  O Enter separado garante que a tecla não é interpretada como parte do texto.
  O hint reforça a ação esperada — mesmo que o agente não processe
  automaticamente, o operador vê o que fazer.
- **Onde se aplica**: tanto no deliver do daemon quanto no poke manual sem
  daemon (`sac send`).
- **Por que não aumentar o sleep para 1s?**: 0.2s já é suficiente para o
  tmux processar o buffer. 1s atrasaria a entrega desnecessariamente.
- **Teste de regressão**: mockar `tmux.send_keys` e verificar chamadas em dois
  passos com delay. O delay real não é testado em unidade (só aceitação manual).

### D5. Teste real ao vivo — requisito obrigatório

**Lições da v1.4 e v1.5**: ambas passaram no gate do code-auditor com suíte
100% verde, mas bugs apareceram ao vivo. A validação estática + testes
unitários não pegam problemas de interação com tmux real e harness real.

- **Escolha**: após todo o código implementado e suíte verde, submeter UM
  ciclo real de mensageria (leader→dev-1→reply→leader) na sessão ativa e
  verificar: (a) mensagem chega no dev-1, (b) dev-1 envia reply, (c) leader
  recebe reply, (d) `sac done` limpa claimed, (e) log.jsonl tem todos os
  eventos, (f) fila não trava para a próxima mensagem.
- **Se o teste falhar**: abortar o commit, corrigir, re-testar.
- **Documentação**: registrar o resultado do teste real no relatório de
  encerramento (findings da change).

## Risks / Trade-offs

- **[R1] Write-ahead log pode registrar done que nunca completa** (crash entre
  log e move): o log terá um evento done sem o arquivo correspondente em done/.
  Na prática, isso é inofensivo — o log é append-only e o arquivo ainda está em
  claimed/ (porque o move não aconteceu). Na re-execução, o agente pode tentar
  `sac done` novamente (arquivo ainda em claimed), e o done idempotente
  (verificar se já está em done antes de mover) evitará duplicatas.
- **[R2] Delay de 0.2s acumula**: em runs com ~100 mensagens, 20s de overhead.
  Aceitável — confiabilidade > throughput para mensageria de coordenação.
- **[R3] SAC_ROOT absoluto obrigatório**: pode frustrar usuário que tenta
  `--sac-root .`. Aceitável — o erro orienta a usar o caminho absoluto.
- **[R4] Teste real depende de sessão ativa**: se a sessão tiver caído entre a
  implementação e o teste, o testador precisa subi-la. Documentado no script.

## Rollback Plan

1. **deliver_reply**: reverter alterações em `daemon.py` + `commands.py` (send).
2. **done atomicidade**: reverter `Store.finish()` para ordem antiga (move→log).
3. **SAC_ROOT**: remover campo `root` de `Config`, reverter `Store.__init__`.
4. **Poke Enter**: reverter `daemon.py` e helpers de send-keys para sem delay.
5. **Teste real**: sem rollback — é procedimento, não código.
