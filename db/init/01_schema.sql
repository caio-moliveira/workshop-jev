-- Banco de vendas da empresa fictícia Mercado Jornada (SPEC-07).
-- Roda uma vez, na primeira subida do container com o volume vazio.

CREATE TABLE regioes (
    id   integer PRIMARY KEY,
    nome text NOT NULL UNIQUE
);

CREATE TABLE categorias (
    id   integer PRIMARY KEY,
    nome text NOT NULL UNIQUE
);

CREATE TABLE produtos (
    id           integer PRIMARY KEY,
    categoria_id integer NOT NULL REFERENCES categorias (id),
    nome         text NOT NULL UNIQUE,
    preco_lista  numeric(12, 2) NOT NULL CHECK (preco_lista > 0),
    custo        numeric(12, 2) NOT NULL CHECK (custo > 0)
);

CREATE TABLE vendedores (
    id        integer PRIMARY KEY,
    nome      text NOT NULL UNIQUE,
    regiao_id integer NOT NULL REFERENCES regioes (id)
);

CREATE TABLE clientes (
    id        integer PRIMARY KEY,
    nome      text NOT NULL UNIQUE,
    segmento  text NOT NULL CHECK (segmento IN ('Varejo', 'PME', 'Corporativo')),
    regiao_id integer NOT NULL REFERENCES regioes (id)
);

CREATE TABLE pedidos (
    id          integer PRIMARY KEY,
    cliente_id  integer NOT NULL REFERENCES clientes (id),
    vendedor_id integer NOT NULL REFERENCES vendedores (id),
    data_pedido date NOT NULL,
    status      text NOT NULL CHECK (status IN ('faturado', 'cancelado'))
);

CREATE TABLE itens_pedido (
    id             integer PRIMARY KEY,
    pedido_id      integer NOT NULL REFERENCES pedidos (id),
    produto_id     integer NOT NULL REFERENCES produtos (id),
    quantidade     integer NOT NULL CHECK (quantidade > 0),
    preco_unitario numeric(12, 2) NOT NULL CHECK (preco_unitario > 0),
    desconto       numeric(4, 2) NOT NULL DEFAULT 0 CHECK (desconto >= 0 AND desconto < 1)
);

CREATE TABLE metas (
    vendedor_id integer NOT NULL REFERENCES vendedores (id),
    mes         date NOT NULL,  -- primeiro dia do mês
    valor_meta  numeric(12, 2) NOT NULL CHECK (valor_meta > 0),
    PRIMARY KEY (vendedor_id, mes)
);

CREATE INDEX pedidos_data_idx ON pedidos (data_pedido);
CREATE INDEX itens_pedido_pedido_idx ON itens_pedido (pedido_id);
