<!-- SPDX-License-Identifier: MPL-2.0 -->
# Cambios de Zadry sobre rx3-toolkit (MPL-2.0)

Copia de trabajo de https://github.com/Tratosca/rx3-toolkit (rama principal, copiada el 2026-10-12). Los archivos modificados siguen bajo MPL-2.0.
Para la revisión legal: ver la nota "LICENCIA" de ZadryStudio/CLAUDE.md.

## 2026-10-12: el bajo como cuarto stem independiente (módulo stems)
Antes: un archivo `.rx3bass` se cargaba pero "seguía al INST" (sin pad ni botón propios) y el INST incluía el bajo.
Ahora: el bajo es un rol propio (bit 8). Sin archivo `.rx3bass` no cambia nada (tres controles y el pad 8 conserva su bucle nativo).

| Archivo | Cambio |
|---|---|
| `mod/modules/stems/rx3_stems_audio.h` | `stems_available`: máscara de 3 a 4 bits (`& 15u`); `stems_mix`: el nivel del bajo es su propio hueco (3) en lugar del del INST, así INST = mezcla − voz − batería − bajo |
| `mod/modules/stems/rx3_stems_panel.h` | `stems_display_order = {1,2,4,8}` (pad 8 = bajo); color del pad 8 ámbar; texto `BASS`; color del botón en pantalla `0xfd20`; subtítulo/etiqueta del cuarto botón |

Sin tocar (ya preparado para cuatro roles): el cargador (`rx3_stems_loader.h`, máscara `(2<<n)-1`), el panel (4 widgets), el atlas de letras (A–Z completo) y la onda por stem (ya entiende la máscara 8 y `available & 0xd`).

## Cómo construir y probar
```
$env:Path += ';C:\Program Files\LLVM\bin'
cd D:\MOLE\rx3-mod
mkdir C:\ruta\salida
python -m app.runtime.cli build --firmware 1.19 --patch stems --patch logging --key C:\ruta\aes256.key --output C:\ruta\salida
```
Copiar `autoexec.bin` al USB (raíz), expulsar, probar en la mesa, y leer `RX3_RUNTIME/session.txt` y `mod.txt`.
Esperado en `session.txt`: `SLIP LOOP: pads 5=instrumental, 6=vocal, 7=drums ...` (el texto del registro sigue siendo el antiguo; el reparto real lo cambia `stems_display_order`)
y en `mod.txt`: `stems ready, available roles = 4`.

## 2026-10-12: script de construcción `zadry_build.py`
Una sola orden para elegir módulos y meter un logo propio (`app.services.logo.files` convierte un PNG a los dos contenedores y `build_runtime(supplied_files=...)` los mete en la imagen).
```
python zadry_build.py --list
python zadry_build.py --out C:\ruta\salida                      # stems + registro + samples
python zadry_build.py --out C:\ruta\salida --logo mi-logo.png    # + logo (añade el módulo 'logo')
```

## 2026-10-12: samples con settings.txt (módulo samples)
Chrome no deja crear archivos `.ini` desde una página web ("Name is not allowed"), pero el módulo exige `settings.ini`. `mod/modules/samples/module.sh`:
si el banco no tiene `settings.ini` pero sí `settings.txt`, se usa ese (mismo contenido y formato); `settings.txt` entra también en la huella de cambios del banco.
La web escribe `settings.txt` siempre (e intenta `settings.ini`). Ruta real del banco: `RX3_RUNTIME/samples/banks/<banco>/` y `RX3_RUNTIME/samples/active`.
Hay que RECONSTRUIR el mod (`python zadry_build.py --out ...`) para que lo lleve.

## 2026-10-12: diagnóstico del sonido de los samples (módulo samples)
En la mesa los pads se iluminan pero no suena nada. El mod cargó el banco (`sample loaded, pad = 1..8`) y aceptó `settings.txt`, pero no registra qué pasa al pulsar.
`rx3_samples_state.h` / `rx3_samples_feature.h`: dos contadores atómicos (llamadas del gancho del bus master y bloques con voz activa; solo cuentan en el hilo de audio, sin E/S) y, al pulsar un pad, se escriben en el registro:
`sample press, pad = N`, `sample master hook calls = X`, `sample blocks with a voice = Y`, `sample voices active = Z`, `sample pad has audio (1/0) = A`.
Interpretación: X = 0 -> la mesa nunca llama al gancho del bus master (el punto de enganche 0x0009c750 no se ejecuta); X > 0 e Y = 0 -> el gancho corre pero la voz no arranca; Y > 0 -> mezcla pero no se oye (nivel/escala).

## 2026-10-13: samples sin sonido — causa probable: escala del bus master (módulo samples)
Registro de la mesa tras pulsar pads: `master hook calls` sube sin parar (22 mil a 81 mil), `blocks with a voice` sube y `voices active` va de 0 a 3, `pad has audio = 1`:
el gancho corre y las voces se mezclan, pero no se oye nada. Hipótesis: el bus master lleva floats en rango PCM16 (hasta 32768) y no normalizados (±1); el mezclador suma
`dato_pcm16 * vol² * 0.5 / 32768`, o sea ±0,5, inaudible en esa escala.
Cambio: `samples_master` mide el pico real del bus ANTES de sumar (`block_peak`, abs a mano, sin libm); si supera `SAMPLES_PCM16_PEAK` (256) activa `samples_scale_int16` y
`samples_mix` multiplica el nivel por 32768 (nuevo parámetro `scale`). El registro al pulsar un pad añade:
`sample master peak x1000 since last press = N` (N/1000 = pico del bus; ~1000 si va normalizado, millones si va en PCM16) y `sample master scale is PCM16 (1/0) = X`.
Limite: si nunca ha sonado una pista desde el arranque, la escala no se ha medido y los samples seguirán inaudibles hasta que suene una.

## 2026-10-13 (2): descartada la escala; prueba del pitido (módulo samples)
Registro con el mod de escala adaptativa: `master peak x1000` ≈ 232..252 (pico ≈ 0,24) y `scale is PCM16 = 0` en todas las pulsaciones: el bus va NORMALIZADO, así que la suma (±0,35) no era inaudible por escala.
Defaults de ganancia correctos (SAMPLES_GAIN_UNITY 100, volumen 100 = ±0,5). Nueva prueba: al pulsar cualquier pad se añade ~1 s de un pitido cuadrado de 441 Hz (amplitud 0,12) al bus,
independiente de las voces, y se registra `sample master peak AFTER mix x1000` (pico tras mezclar). Si el pitido SE OYE: escribir en el bus llega a los altavoces y el fallo está en la mezcla de samples.
Si NO se oye: el punto de enganche del bus master (0x0009c750) no es la salida real (se sobrescribe, o es otro bus) y hay que buscar otro punto.

## 2026-10-13 (3): CAUSA REAL de los samples mudos (módulo samples)
`samples_publish_config` solo copiaba colores y volumen. `samples_config.gain[]` (trim por pad) y `.mode[]` quedaban en 0 (variable estática), y al pulsar el pad la voz
copiaba trim = 0 -> `level = gain * 0 = 0`: la voz arrancaba, sonaba "mezclando" y sumaba silencio. (El pitido sí se oía porque no depende del trim.)
Arreglo: `samples_publish_config` publica también `gain`, `mode` y `shift_silence`. Diagnóstico añadido al pulsar: frames/pico del dato, volumen, trim y modo.

## 2026-10-13 (4): samples funcionan en la mesa; diagnósticos y pitido retirados
Con el arreglo de `samples_publish_config` suenan los samples. Se quitan el pitido, los contadores y las mediciones de pico; `samples_mix` conserva el parámetro `scale` (siempre 1.0, bus normalizado).
