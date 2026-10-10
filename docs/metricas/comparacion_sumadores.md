# Comparación de sumadores: ripple-carry frente a carry-lookahead

| sumador | ancho | transistores | profundidad | alpha | ms_por_op |
|---|---|---|---|---|---|
| RCA | 8 | 224 | 8 | 0.3653 | 0.08 |
| CLA | 8 | 790 | 11 | 0.3372 | 0.28 |
| RCA | 16 | 448 | 16 | 0.3914 | 0.17 |
| CLA | 16 | 1672 | 14 | 0.3262 | 0.57 |
| RCA | 32 | 896 | 32 | 0.3865 | 0.31 |
| CLA | 32 | 3526 | 19 | 0.3144 | 1.18 |

> La profundidad se mide en celdas primitivas sobre el camino más largo.
