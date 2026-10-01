// Conventional Commits conforme PRD 13.1: `tipo(escopo): descrição`.
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // `data` e `config` são os tipos exigidos para mexer em golden set,
    // fixtures, preços e limiares (PRD 13.4, item 6).
    'type-enum': [2, 'always',
      ['feat', 'fix', 'chore', 'docs', 'data', 'config', 'test', 'refactor', 'ci']],
    // Escopo é opcional (`chore: passo 0, ...` é válido), mas quando existe
    // tem que ser um dos escopos do PRD.
    'scope-enum': [2, 'always',
      ['backend', 'frontend', 'graph', 'providers', 'data', 'config', 'docs']],
  },
};
