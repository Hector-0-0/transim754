## Resumen
<!-- Qué cambia y por qué. Una o dos oraciones. -->

Closes #

## Módulo
<!-- core · cells · blocks · alu · fpu-common · fpu-addsub · fpu-muldiv · cpu · metrics · ai · cli · gui · docs · research -->

## Evidencia
<!-- Pega el resumen de `make validar M=<modulo>` (debe decir PASS). -->

```
```

## Definition of Done
- [ ] Las pruebas del módulo pasan y no queda ningún `xfail` propio.
- [ ] `make validar M=<modulo>` da **PASS**.
- [ ] `make lint` y `make typecheck` sin errores.
- [ ] Docstrings completos en todo lo público.
- [ ] GUIA del módulo e `interno/BITACORA.md` actualizadas.
- [ ] Entrada en `interno/REGISTRO_IA.md` si se usó IA.
- [ ] Métricas regeneradas (`make metrics`) si cambió el hardware.
- [ ] No se cambiaron interfaces públicas (o hay un ADR que lo autoriza).
- [ ] Commits con mi identidad, en formato convencional, sin trailers.
- [ ] Revisado por otro integrante (CODEOWNERS).
