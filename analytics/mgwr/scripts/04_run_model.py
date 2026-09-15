"""
04_run_model.py -- v1 EXPLORATORIO
------------------------------------
Bloque 5 (MGWR/PTNA) -- Subtarea 5.2: corre MGWR sobre el dataset filtrado.

Esta es deliberadamente una version liviana: el dataset todavia no tiene
sentimiento_medio (bloqueante activo, ver docs/contexto_maestro_proyecto_ptna.md
seccion 6, Hallazgo 3), asi que no vale la pena gastar el computo completo de
precision -- esto se va a volver a correr cuando esa variable este disponible.

NOTA SOBRE LA API DE mgwr (importante, no es un detalle menor): a diferencia
del pseudocodigo de referencia (`bw = Sel_BW(...).search(); MGWR(coords, y, X,
bw)`), la clase real `MGWR` de la libreria `mgwr` 2.x NO acepta un bandwidth
escalar -- exige un objeto `selector` (un `Sel_BW` con multi=True ya resuelto
via .search()), porque MGWR es multiescala: cada variable X termina con su
propio bandwidth, no uno solo compartido. Ademas, el backfitting (los
coeficientes locales) se calcula DENTRO de `Sel_BW.search()`, no dentro de
`MGWR.fit()` -- `.fit()` solo calcula predy y diagnosticos a partir de eso.
Esto significa que no existe una forma directa en la API publica de "inyectar"
un bandwidth ya conocido (encontrado en el submuestreo) en el dataset
completo sin volver a pasar por `Sel_BW.search()`. La solucion usada aca:
correr `Sel_BW(...).search()` una segunda vez sobre el dataset completo, pero
con `multi_bw_min = multi_bw_max = bandwidth_del_submuestreo` -- esto evita
la busqueda cara del bandwidth optimo (ya se hizo, mas barato, en el
submuestreo) pero sigue ejecutando el backfitting multiescala real sobre
todas las filas, que es donde vive el costo de computo inevitable.

NOTA SOBRE KERNEL ADAPTATIVO vs FIJO (incidente real, no preventivo): la
primera corrida contra el dataset filtrado real fallo con
`LinAlgError: A singular matrix detected` durante Sel_BW().search() sobre el
submuestreo, con kernel `fixed=True` (bandwidth = radio en grados, EPSG:4326).
Se diagnostico (ver analisis fuera de este script) que las 9 variables X
tienen varianza normal en el submuestreo (no hay columna constante) y no hay
coordenadas duplicadas -- la causa real es que la distancia al vecino mas
cercano en este dataset es de apenas ~0.009 grados, y durante la busqueda por
seccion aurea el algoritmo prueba candidatos de bandwidth cada vez mas chicos;
en algun punto un candidato queda por debajo de esa distancia minima y una o
mas ventanas locales se quedan sin vecinos suficientes -> matriz de diseno
singular, sin importar que tan bien condicionadas esten las variables. Por
eso la busqueda sobre el submuestreo usa kernel ADAPTATIVO (`fixed=False`,
bandwidth = cantidad de vecinos, no distancia): garantiza un minimo de puntos
en cada ventana local sin importar la escala/densidad de las coordenadas. El
bandwidth resultante queda expresado en "cantidad de vecinos", no en grados
-- por eso el fit final sobre el dataset completo (que reutiliza ese numero
via multi_bw_min=multi_bw_max) tambien tiene que usar `fixed=False`: si se
dejara `fixed=True` ahi, ese mismo numero (p.ej. 150) se reinterpretaria como
"150 grados de radio" -- una ventana que cubre la isla entera muchas veces,
degenerando el modelo a algo global sin fallar con ningun error. No es una
opcion, es una consecuencia obligada de que el bandwidth y el tipo de kernel
viajan juntos.

NOTA SOBRE TRANSFERIR BANDWIDTH ADAPTATIVO ENTRE DATASETS DE DISTINTA DENSIDAD
(segundo incidente real, tras el del kernel fijo de arriba): con el kernel ya
en modo adaptativo, la siguiente corrida fallo igual con el mismo
LinAlgError, pero esta vez durante el fit sobre el DATASET COMPLETO, no en la
busqueda sobre el submuestreo (esa ya termino bien). La razon: un bandwidth
adaptativo es una CANTIDAD DE VECINOS, no una distancia fisica, y esa cantidad
no es transferible tal cual entre dos datasets con distinta densidad de
puntos sobre la MISMA area geografica. La submuestra (860 filas) tiene ~1/3
de la densidad del dataset completo (2579 filas) en la misma zona de
Tenerife -- reusar el mismo numero de vecinos crudo en el dataset completo
selecciona una ventana geografica ~3 veces mas chica que la que tenia
sentido en la submuestra, lo que aumenta el riesgo de colinealidad local
(alguna combinacion de variables queda casi constante dentro de esa ventana
angosta) -> matriz de diseno local singular. Fix: reescalar cada bandwidth
por la razon de tamaños (n_total / n_submuestra) antes de aplicarlo, con un
piso de seguridad para no terminar con ventanas demasiado chicas incluso
despues del reescalado.

Investigando el traceback real (linea por linea contra el codigo fuente de
`mgwr`, no por prueba y error) aparecio ademas un problema mas sutil que el
reescalado por si solo NO resuelve: el backfitting multiescala arranca con
un paso "semilla" (`multi_bw()` en `mgwr/search.py`) que ajusta una UNICA
regresion GWR con TODAS las variables juntas (intercepto + 9) para
inicializar los residuos antes de iterar variable por variable. Ese paso
semilla hace su PROPIA busqueda de bandwidth con golden-section, y esa
busqueda especifica **no respeta `multi_bw_min`/`multi_bw_max`** -- son
parametros que la propia libreria solo aplica al loop de backfitting por
variable, no al paso semilla (confirmado leyendo `mgwr/search.py::multi_bw`
y `mgwr/sel_bw.py::_mbw`). Es decir: por mas que se reescalen y acoten los
9 bandwidths por variable, el paso semilla queda libre de explorar
candidatos chicos por su cuenta sobre las 9 variables juntas -- y con mas
variables a la vez el riesgo de colinealidad local es todavia mayor que en
cualquier regresion univariada. Este es casi con seguridad el paso que
realmente fallo (se confirmo por separado, evaluando ese mismo ajuste de
forma aislada con un bandwidth amplio: funciona sin error). La API si expone
una salida: `Sel_BW.search(..., init_multi=<bandwidth>)` fija el bandwidth
semilla directamente, evitando que se dispare esa busqueda no controlada.
Se usa `init_multi = n_total` (todo el dataset) -- para un paso que ocurre
una sola vez y solo sirve para inicializar el backfitting, un bandwidth
amplio es la opcion mas segura y no tiene costo de precision relevante,
porque el resultado final de cada variable lo determina su propio bandwidth
(ya fijado) durante las iteraciones de backfitting que siguen.

NOTA SOBRE VISIBILIDAD DURANTE EL FIT FINAL (tercer ajuste, no cambia nada
del calculo de arriba): con el reescalado por densidad ya andando, una
corrida real se tuvo que cortar manualmente tras 6+ minutos sin ningun
output nuevo -- sin loguear nada propio del script en ese tramo, no habia
forma de distinguir "sigue calculando" de "se colgo" sin abrir el
Administrador de Tareas de Windows. mgwr no expone un callback de progreso
entre rondas de backfitting, pero si expone `verbose=True` en
`Sel_BW.search()`, que imprime -- directo a stdout, no como valor de
retorno -- el numero de ronda, el criterio real de convergencia ("SOC",
magnitud del cambio de coeficientes entre rondas) y los bandwidths de esa
ronda; se activo. Como una sola ronda puede tardar varios minutos con 2579
puntos (no hay progreso visible DENTRO de una ronda, solo entre rondas), el
fit final ahora corre en un proceso aparte (mismo mecanismo que la busqueda
sobre el submuestreo) para poder emitir un heartbeat propio cada 60s
mientras corre, con timeout generoso (default 40 min) como red de seguridad
para no quedar colgado indefinidamente -- a diferencia del timeout de la
busqueda sobre el submuestreo, aca el objetivo principal es visibilidad, no
un limite estricto. El diagnostico de matrices singulares que ya existia
(ver mas arriba) se movio adentro de ese proceso aparte, sin cambiar su
logica.

NOTA SOBRE EL TIMEOUT DE LA BUSQUEDA SOBRE EL SUBMUESTREO (cuarto ajuste,
tampoco cambia el calculo): una corrida real con el reescalado por densidad
ya funcionando bien fue matada por el timeout de 15 min estando en la
iteracion 21/50 (13:48 min transcurridos, ~40-60s por iteracion, sin ningun
signo de problema numerico -- simplemente el timeout resulto ajustado para
esa corrida en particular; otra corrida previa habia tardado 9:13 en total
para el mismo paso). Default subido a 30 min. Ademas, `_bw_search_worker`
ahora corre con `verbose=True` y envuelve su stdout (`_IterationWatcher`)
para que, si hay que matar el proceso de nuevo, el `TimeoutError` diga en
que iteracion iba -- sin ese dato, no hay forma de saber de un vistazo si
conviene subir el timeout (si iba cerca del final) o `--subsample-step`
(si iba lejos, cada iteracion es cara). `--subsample-step` y
`--bw-search-timeout-min` ya eran parametrizables por linea de comandos
desde que se escribio el script -- no hizo falta agregar flags nuevos, solo
subir el default del segundo y mejorar el mensaje de error.

Uso:
    python 04_run_model.py
    python 04_run_model.py --subsample-step 4 --max-iter-multi 30
    python 04_run_model.py --full-fit-timeout-min 60
    python 04_run_model.py --bw-search-timeout-min 45 --subsample-step 4
"""

import argparse
import multiprocessing
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import DATA_INTERIM_DIR, PTNA_QUALITY_COLUMNS, setup_logging

SCRIPT_NAME = "04_run_model"

COORD_COLUMNS = ["centroide_lon", "centroide_lat"]
Y_COLUMN = "densidad_plazas_km2"


def spatial_subsample_indices(lon: np.ndarray, lat: np.ndarray, step: int) -> np.ndarray:
    """
    Indices de un submuestreo espacial (1 de cada `step` filas) que preserva
    dispersion geografica, ordenando por curva de Morton (Z-order) en vez de
    tomar aleatoriedad pura o las primeras N filas (que podrian quedar todas
    concentradas en una esquina del mapa).
    """
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    def _to_uint16(values: np.ndarray) -> np.ndarray:
        vmin, vmax = values.min(), values.max()
        if vmax == vmin:
            return np.zeros(len(values), dtype=np.uint64)
        norm = (values - vmin) / (vmax - vmin)
        return np.clip(norm * 65535, 0, 65535).astype(np.uint64)

    def _spread_bits(x: np.ndarray) -> np.ndarray:
        x = (x | (x << 8)) & 0x00FF00FF
        x = (x | (x << 4)) & 0x0F0F0F0F
        x = (x | (x << 2)) & 0x33333333
        x = (x | (x << 1)) & 0x55555555
        return x

    morton = (_spread_bits(_to_uint16(lat)) << 1) | _spread_bits(_to_uint16(lon))
    order = np.argsort(morton, kind="stable")
    return order[::step]


def _local_design_matrix_problems(coords, X, bw, h3_index, cond_threshold=1e12):
    """
    Replica el calculo interno de mgwr (peso bisquare adaptativo + matriz de
    diseno ponderada local, ver mgwr/kernels.py::Kernel y
    spglm/iwls.py::_compute_betas_gwr) para CADA punto, y devuelve la lista de
    (h3_index, numero_de_condicion) de los puntos cuya matriz local es
    singular o esta peligrosamente mal condicionada.

    Se usa solo como diagnostico DESPUES de que el fit real falla (ver
    excepcion en main()) -- no reemplaza el fit, solo permite identificar
    hexagonos puntuales para decidir si excluirlos manualmente en vez de
    quedarse con un traceback generico sin ninguna pista de donde esta el
    problema real.
    """
    from mgwr.kernels import Kernel

    coords_arr = np.asarray(coords)
    n = len(coords_arr)
    problems = []
    for i in range(n):
        k = Kernel(i, coords_arr, bw=bw, fixed=False, function="bisquare")
        wi = k.kernel
        xtx = (X * wi[:, None]).T @ X
        try:
            cond = np.linalg.cond(xtx)
        except np.linalg.LinAlgError:
            cond = np.inf
        if not np.isfinite(cond) or cond > cond_threshold:
            problems.append((str(h3_index[i]), float(cond)))
    return problems


class _IterationWatcher:
    """Envuelve stdout del proceso hijo para detectar las lineas
    'Current iteration: N ,SOC: ...' que imprime mgwr (verbose=True) y
    actualizar un contador compartido (multiprocessing.Value) con la ultima
    iteracion vista -- sin dejar de imprimir normalmente (se ve en vivo en la
    terminal igual que antes). No parchea nada de la logica interna de mgwr,
    solo lee lo que la libreria ya imprime por su cuenta.

    Motivo (incidente real): si el timeout mata el proceso a mitad de
    camino, sin esto no hay forma de saber -- ni en consola ni en el log --
    en que iteracion iba, lo cual es justo el dato que hace falta para
    decidir si conviene subir el timeout o subir --submuestreo-cada (ver
    TimeoutError en run_bw_search_with_timeout)."""

    _patron = re.compile(r"Current iteration:\s*(\d+)")

    def __init__(self, stream_real, contador_compartido):
        self._stream_real = stream_real
        self._contador = contador_compartido
        self._buffer = ""

    def write(self, data):
        self._stream_real.write(data)
        self._buffer += data
        while "\n" in self._buffer:
            linea, self._buffer = self._buffer.split("\n", 1)
            m = self._patron.search(linea)
            if m:
                self._contador.value = int(m.group(1))

    def flush(self):
        self._stream_real.flush()


def _bw_search_worker(coords, y, X, max_iter_multi, ultima_iteracion, result_queue):
    """Corre en un proceso aparte para poder aplicarle un timeout duro (ver run_bw_search_with_timeout).

    fixed=False (kernel ADAPTATIVO, bandwidth = cantidad de vecinos) en vez de
    fixed=True (kernel fijo, bandwidth = radio en grados) -- ver nota extensa
    al principio del archivo sobre el LinAlgError real que este cambio resuelve.
    Cuesta un poco mas de computo que un kernel fijo, aceptable porque esto
    corre solo sobre el submuestreo, no sobre el dataset completo.

    verbose=True + _IterationWatcher: solo para que, si hay que matar el
    proceso por timeout, el mensaje de error pueda decir en que iteracion
    iba (ver incidente real documentado en _IterationWatcher). No cambia el
    resultado de la busqueda en nada.
    """
    sys.stdout = _IterationWatcher(sys.stdout, ultima_iteracion)
    try:
        from mgwr.sel_bw import Sel_BW

        selector = Sel_BW(coords, y, X, multi=True, fixed=False)
        bw = selector.search(max_iter_multi=max_iter_multi, verbose=True)
        result_queue.put(("ok", np.asarray(bw, dtype=float)))
    except Exception as exc:  # noqa: BLE001 -- se reporta al proceso padre, no se traga en silencio
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def run_bw_search_with_timeout(coords, y, X, max_iter_multi, timeout_seconds, logger):
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    ultima_iteracion = ctx.Value("i", 0)
    process = ctx.Process(
        target=_bw_search_worker,
        args=(coords, y, X, max_iter_multi, ultima_iteracion, result_queue),
    )

    logger.info(
        "Lanzando Sel_BW().search() sobre el submuestreo en un proceso aparte (limite: %.0f min)...",
        timeout_seconds / 60,
    )
    process.start()
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join()
        iteracion_alcanzada = ultima_iteracion.value
        elapsed_min = timeout_seconds / 60
        timeout_msg = (
            f"Sel_BW().search() supero el limite de {elapsed_min:.0f} minutos sobre el "
            f"submuestreo ({len(coords)} filas). Completo {iteracion_alcanzada}/{max_iter_multi} "
            f"iteraciones de backfitting en esos {elapsed_min:.0f} min antes de matarlo -- si iba "
            f"cerca del final, probablemente alcance con subir --bw-search-timeout-min; si iba lejos, "
            f"conviene tambien subir --subsample-step para abaratar cada iteracion. Proceso terminado."
        )
        logger.error(timeout_msg)
        raise TimeoutError(timeout_msg)

    if result_queue.empty():
        raise RuntimeError(
            f"El proceso de busqueda de bandwidth termino sin devolver resultado "
            f"(exit code: {process.exitcode}). Revisar el log para mas contexto."
        )

    status, payload = result_queue.get()
    if status == "error":
        raise RuntimeError(f"Sel_BW().search() fallo dentro del proceso hijo: {payload}")
    return payload


def _full_fit_worker(coords, y, X, bw_bounds, init_multi_bw, max_iter_multi, quality_columns, h3_values, result_queue):
    """
    Corre en un proceso aparte, igual que _bw_search_worker -- pero esta vez el
    objetivo no es poder matarlo (aunque el padre igual puede hacerlo si de
    verdad se cuelga, ver run_full_fit_with_progress), sino poder MOSTRAR
    PROGRESO mientras corre. Incidente real que motiva esto: el fit sobre el
    dataset completo se tuvo que cortar tras 6+ minutos sin ningun output
    nuevo, sin poder distinguir "sigue trabajando" de "esta colgado" sin abrir
    el Administrador de Tareas de Windows.

    verbose=True en .search() activa el hook NATIVO de mgwr (mgwr/search.py::
    multi_bw) que imprime, al terminar cada ronda de backfitting, el numero de
    ronda, el criterio real de convergencia ("SOC" -- magnitud del cambio de
    coeficientes entre rondas, lo que de verdad determina cuando termina el
    backfitting) y los bandwidths de esa ronda. mgwr no expone esto como
    callback, solo como print()/tqdm directo -- no hay forma de agregarle
    timing propio sin parchear la libreria por dentro. Este proceso hijo
    comparte la consola con el padre (multiprocessing no la redirige), asi que
    esos mensajes SE VEN EN VIVO en la terminal sin hacer nada especial. Se
    intento ademas duplicarlos al archivo de log (redirigiendo stdout del
    proceso hijo), pero se descarto: tqdm escribe por defecto a stderr, no a
    stdout, asi que la barra de "Backfitting: X/Y" quedaba afuera de esa
    redireccion igual, y el resultado era una captura parcial y potencialmente
    enganosa (alguien mirando el .log podria pensar que tiene el registro
    completo de las rondas y no es asi). Mejor ser explicitos: el detalle de
    convergencia por ronda (SOC, bandwidths) se ve en la TERMINAL en vivo, no
    queda en el archivo .log -- lo que si queda en el .log (y en stdout, ver
    run_full_fit_with_progress) es el inicio, el heartbeat cada 60s, y el fin
    del paso completo.
    """
    try:
        from mgwr.gwr import MGWR
        from mgwr.sel_bw import Sel_BW

        selector_full = Sel_BW(coords, y, X, multi=True, fixed=False)
        selector_full.search(
            multi_bw_min=bw_bounds, multi_bw_max=bw_bounds,
            init_multi=init_multi_bw, max_iter_multi=max_iter_multi, verbose=True,
        )
        model = MGWR(coords, y, X, selector_full, fixed=False, name_x=quality_columns).fit()

        result_queue.put(("ok", {
            "params": model.params,
            "predy": model.predy,
            "bandwidths_full": np.asarray(selector_full.bw[0], dtype=float),
        }))
    except Exception as exc:  # noqa: BLE001 -- se reporta al padre con diagnostico, no se traga en silencio
        # Mismo diagnostico de matrices locales que antes (ver _local_design_matrix_problems),
        # ahora corrido aca porque el fit real tambien corre aca.
        n_total_local = len(coords)
        X_with_intercept = np.column_stack([np.ones(n_total_local), X])
        seed_problems = _local_design_matrix_problems(coords, X_with_intercept, init_multi_bw, h3_values)

        var_problems = {}
        for j, varname in enumerate(quality_columns):
            probs = _local_design_matrix_problems(coords, X[:, [j]], float(bw_bounds[j]), h3_values)
            if probs:
                var_problems[varname] = probs

        result_queue.put(("error_with_diagnostics", {
            "error_type": type(exc).__name__,
            "error_msg": str(exc),
            "seed_problems": seed_problems,
            "var_problems": var_problems,
        }))


def run_full_fit_with_progress(coords, y, X, bw_bounds, init_multi_bw, max_iter_multi,
                                quality_columns, h3_values, timeout_seconds, logger):
    """
    Lanza _full_fit_worker en un proceso aparte y hace polling sobre la propia
    cola de resultado (result_queue.get(timeout=60)) en vez de sobre
    process.join(timeout=60) -- CRITICO: no es un detalle de estilo. El
    resultado de este worker (params + predy, del orden de cientos de KB para
    un dataset real) es mucho mas grande que el de la busqueda sobre el
    submuestreo (un puñado de floats), y multiprocessing.Queue en Windows usa
    un pipe con buffer limitado: si el proceso hijo intenta poner un objeto
    que no entra entero en ese buffer y el padre esta bloqueado en
    process.join() SIN estar leyendo la cola todavia, hijo y padre quedan
    mutuamente esperando (el hijo no puede terminar de escribir en el pipe, el
    padre no chequea la cola hasta que el hijo termine) -- deadlock real,
    confirmado en esta misma sesion (el hijo llegaba a imprimir "Inference:
    100%" y despues no pasaba nada mas, ni timeout ni heartbeat). Por eso el
    polling de abajo lee la cola con timeout en vez de esperar a que el
    proceso muera primero.

    Cada vez que el timeout de result_queue.get() vence sin resultado, se
    imprime un heartbeat con el tiempo transcurrido (a archivo Y a stdout). Si
    se supera timeout_seconds, recien ahi se mata el proceso -- a diferencia
    de la busqueda sobre el submuestreo (run_bw_search_with_timeout), el
    objetivo principal aca es visibilidad, no un limite estricto; el timeout
    queda como red de seguridad para no quedar colgado indefinidamente.
    """
    import queue as _queue_mod

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_full_fit_worker,
        args=(coords, y, X, bw_bounds, init_multi_bw, max_iter_multi, quality_columns, h3_values, result_queue),
    )

    start_msg = (
        f"Iniciando fit final sobre dataset completo ({len(coords)} filas) -- esto puede tardar "
        f"varios minutos por ronda de backfitting, sin actualizacion visible entre rondas mas alla "
        f"de lo que imprima mgwr mismo (ver mensajes 'Backfitting'/'Current iteration' abajo) y el "
        f"heartbeat cada 60s de este script. Limite antes de terminar el proceso: {timeout_seconds/60:.0f} min."
    )
    logger.info(start_msg)
    print(start_msg)

    heartbeat_interval_s = 60
    t_start = time.perf_counter()
    process.start()

    status = None
    payload = None
    while True:
        try:
            status, payload = result_queue.get(timeout=heartbeat_interval_s)
            break
        except _queue_mod.Empty:
            pass

        elapsed = time.perf_counter() - t_start
        if elapsed > timeout_seconds:
            process.terminate()
            process.join()
            timeout_msg = (
                f"El fit final sobre el dataset completo supero el limite de "
                f"{timeout_seconds / 60:.0f} min sin terminar (tiempo transcurrido: "
                f"{elapsed / 60:.1f} min). Proceso terminado."
            )
            logger.error(timeout_msg)
            print(timeout_msg)
            raise TimeoutError(timeout_msg)

        if not process.is_alive():
            # El proceso murio sin poner nada en la cola (crash antes de llegar
            # al except propio, o el pipe se corto) -- no tiene sentido seguir
            # esperando un resultado que nunca va a llegar.
            raise RuntimeError(
                f"El proceso del fit final termino (exit code: {process.exitcode}) sin devolver "
                f"resultado. Revisar el log para mas contexto."
            )

        heartbeat_msg = f"[heartbeat] Fit final sigue corriendo -- transcurridos {elapsed / 60:.1f} min."
        logger.info(heartbeat_msg)
        print(heartbeat_msg)

    process.join()  # ya tenemos el resultado, esto deberia ser practicamente instantaneo

    total_elapsed = time.perf_counter() - t_start
    done_msg = f"Proceso del fit final termino (exito o error) en {total_elapsed / 60:.1f} min."
    logger.info(done_msg)
    print(done_msg)

    if status == "ok":
        return payload

    if status == "error_with_diagnostics":
        seed_problems = payload["seed_problems"]
        var_problems = payload["var_problems"]

        if seed_problems:
            logger.error(
                "Paso SEMILLA (intercepto + %d variables, bw=%d): %d hexagonos con matriz singular/mal "
                "condicionada. Ejemplos (hasta 20): %s",
                len(quality_columns), int(init_multi_bw), len(seed_problems), seed_problems[:20],
            )
        for varname, probs in var_problems.items():
            logger.error(
                "Variable %s: %d hexagonos con matriz singular/mal condicionada. Ejemplos (hasta 20): %s",
                varname, len(probs), probs[:20],
            )

        if not seed_problems and not var_problems:
            logger.error(
                "El diagnostico de matrices locales no encontro ningun punto singular/mal condicionado "
                "con los bandwidths usados -- la causa real de este fallo no quedo identificada por este "
                "chequeo puntual."
            )
            raise RuntimeError(f"{payload['error_type']}: {payload['error_msg']}")

        resumen = {"semilla": len(seed_problems), **{k: len(v) for k, v in var_problems.items()}}
        raise RuntimeError(
            f"El fit sobre el dataset completo fallo con matriz de diseno singular "
            f"({payload['error_type']}: {payload['error_msg']}). Hexagonos problematicos por bloque: "
            f"{resumen}. Ver analytics/mgwr/logs/{SCRIPT_NAME}.log para la lista completa de h3_index "
            f"y decidir si excluirlos manualmente o si el problema es mas generalizado."
        )

    raise RuntimeError(f"El fit final fallo dentro del proceso hijo, respuesta inesperada: {payload}")


def parse_args():
    parser = argparse.ArgumentParser(description="Bloque 5 (MGWR/PTNA) -- v1 exploratorio")
    parser.add_argument(
        "--input",
        default=str(DATA_INTERIM_DIR / "ptna_dataset_filtered.parquet"),
        help="Parquet filtrado de entrada (default: analytics/mgwr/data/interim/ptna_dataset_filtered.parquet)",
    )
    parser.add_argument(
        "--output",
        default=str(DATA_INTERIM_DIR / "ptna_mgwr_model.pkl"),
        help="Ruta del pickle de salida (default: analytics/mgwr/data/interim/ptna_mgwr_model.pkl)",
    )
    parser.add_argument(
        "--subsample-step", type=int, default=3,
        help="1 de cada N filas (orden Morton) para la busqueda de bandwidth (default: 3). "
             "Subilo (ej. 4 o 5) si el timeout de --bw-search-timeout-min se sigue quedando "
             "corto -- menos filas en el submuestreo abarata cada iteracion de backfitting.",
    )
    parser.add_argument(
        "--max-iter-multi", type=int, default=50,
        help="Iteraciones maximas de backfitting MGWR, submuestreo y dataset completo (default: 50)",
    )
    parser.add_argument(
        "--bw-search-timeout-min", type=float, default=30.0,
        help="Limite de tiempo para Sel_BW().search() sobre el submuestreo, en minutos (default: 30). "
             "Subido de 15 a 30 tras una corrida real que llego a 21/50 iteraciones en 13:48 min sin "
             "ningun problema, solo corto por timeout -- 50 iteraciones completas rondarian los 30-33 "
             "min en el peor ritmo visto hasta ahora. Si se sigue quedando corto, considerar tambien "
             "--subsample-step para abaratar cada iteracion en vez de solo subir este limite.",
    )
    parser.add_argument(
        "--full-fit-timeout-min", type=float, default=40.0,
        help="Limite de tiempo para el fit final sobre el dataset completo, en minutos (default: 40). "
             "Se imprime un heartbeat cada 60s mientras corre -- este limite es una red de seguridad, "
             "no el mecanismo principal de visibilidad.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging(SCRIPT_NAME)
    t0 = time.perf_counter()

    try:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"No existe {input_path}. Correr primero 02_filter_nan.py.")

        logger.info("Leyendo %s", input_path)
        df = pd.read_parquet(input_path)
        n_total = len(df)
        logger.info("Filas cargadas: %d", n_total)

        required_cols = PTNA_QUALITY_COLUMNS + COORD_COLUMNS + [Y_COLUMN]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise RuntimeError(f"Faltan columnas esperadas en el dataset filtrado: {missing_cols}.")

        logger.info("Imputando NaN restantes en las 9 variables X con la mediana de cada columna...")
        X_raw = df[PTNA_QUALITY_COLUMNS].copy()
        medians = X_raw.median()
        n_imputed = int(X_raw.isna().sum().sum())
        X_imputed = X_raw.fillna(medians)
        logger.info("Valores imputados por mediana: %d. Medianas usadas: %s", n_imputed, medians.to_dict())

        logger.info("Normalizando las 9 variables X con StandardScaler...")
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imputed.values)

        y = df[[Y_COLUMN]].values.astype(float)
        lon = df["centroide_lon"].values
        lat = df["centroide_lat"].values
        coords_full = list(zip(lon, lat))

        logger.info(
            "Submuestreo espacial (orden Morton/Z): 1 de cada %d filas.", args.subsample_step
        )
        sub_idx = spatial_subsample_indices(lon, lat, args.subsample_step)
        coords_sub = [coords_full[i] for i in sub_idx]
        X_sub = X_scaled[sub_idx]
        y_sub = y[sub_idx]
        logger.info("Filas en el submuestreo: %d / %d", len(sub_idx), n_total)

        lon_sub = lon[sub_idx]
        lat_sub = lat[sub_idx]
        logger.info(
            "Rango centroide_lon en el submuestreo: [%.6f, %.6f] (dataset completo: [%.6f, %.6f])",
            lon_sub.min(), lon_sub.max(), lon.min(), lon.max(),
        )
        logger.info(
            "Rango centroide_lat en el submuestreo: [%.6f, %.6f] (dataset completo: [%.6f, %.6f])",
            lat_sub.min(), lat_sub.max(), lat.min(), lat.max(),
        )

        # Chequeo explicito ANTES de Sel_BW: una columna con varianza ~0 tras el
        # StandardScaler (constante en la submuestra, aunque no lo sea en el
        # dataset completo) produce una matriz de diseno singular sin importar
        # el bandwidth ni el tipo de kernel -- si esto dispara, no tiene sentido
        # seguir a Sel_BW a ciegas, el error ahi seria el mismo pero mas dificil
        # de diagnosticar (ver incidente documentado al principio del archivo).
        variances_sub = X_sub.var(axis=0)
        for name, var in zip(PTNA_QUALITY_COLUMNS, variances_sub):
            logger.info("Varianza de %s (normalizada) en el submuestreo: %.6f", name, var)
        zero_var_cols = [
            name for name, var in zip(PTNA_QUALITY_COLUMNS, variances_sub) if var < 1e-6
        ]
        if zero_var_cols:
            raise RuntimeError(
                f"Varianza ~0 tras normalizar en el submuestreo para: {zero_var_cols}. "
                f"Una columna practicamente constante produce una matriz de diseno singular en "
                f"Sel_BW sin importar el bandwidth -- no tiene sentido seguir. Revisar por que esa(s) "
                f"variable(s) no varia(n) dentro de este submuestreo espacial (subsample-step="
                f"{args.subsample_step}): ¿quedo muy poca dispersion de valores tras el filtro de NaN, "
                f"o el submuestreo cayo todo en una zona geografica homogenea?"
            )

        timeout_seconds = args.bw_search_timeout_min * 60
        t_bw0 = time.perf_counter()
        bw_sub = run_bw_search_with_timeout(
            coords_sub, y_sub, X_sub, args.max_iter_multi, timeout_seconds, logger
        )
        bw_search_elapsed = time.perf_counter() - t_bw0
        logger.info("Bandwidth encontrado sobre el submuestreo en %.1f s: %s", bw_search_elapsed, bw_sub.tolist())

        logger.info(
            "Aplicando ese bandwidth (reescalado por densidad, kernel adaptativo) "
            "sobre el DATASET COMPLETO filtrado (%d filas)...",
            n_total,
        )
        t_fit0 = time.perf_counter()

        # Un bandwidth adaptativo es una CANTIDAD DE VECINOS, no una distancia --
        # no es transferible tal cual entre datasets de distinta densidad de puntos
        # sobre la misma area geografica. Se reescala por la razon de tamaños para
        # preservar una extension geografica equivalente a la que tenia sentido en
        # el submuestreo (ver nota extensa al principio del archivo, segundo
        # incidente). bw_floor evita ventanas demasiado chicas incluso despues del
        # reescalado; el techo es simplemente n_total (no se puede pedir mas
        # vecinos que puntos existen).
        scale_factor = n_total / len(sub_idx)
        bw_floor = max(30, 3 * len(PTNA_QUALITY_COLUMNS))
        bw_rescaled_raw = bw_sub * scale_factor
        bw_rescaled = np.clip(np.round(bw_rescaled_raw), bw_floor, n_total).astype(int)

        logger.info(
            "Razon de reescalado (n_total / n_submuestra): %.3f. Piso de seguridad: %d vecinos.",
            scale_factor, bw_floor,
        )
        for name, raw, final in zip(PTNA_QUALITY_COLUMNS, bw_rescaled_raw, bw_rescaled):
            if int(round(raw)) != int(final):
                logger.warning(
                    "Bandwidth de %s ajustado por piso/techo de seguridad: reescalado=%.1f -> usado=%d",
                    name, raw, final,
                )
            else:
                logger.info("Bandwidth de %s reescalado: %.1f (submuestra) -> %d vecinos", name, raw, final)

        bw_bounds = [float(b) for b in bw_rescaled]

        # init_multi fija el bandwidth del paso "semilla" del backfitting (todas las
        # variables juntas) -- sin esto, mgwr corre su propia busqueda de bandwidth
        # NO controlada por multi_bw_min/multi_bw_max para ese paso especifico (ver
        # nota extensa al principio del archivo). n_total es la opcion mas segura:
        # el paso semilla ocurre una sola vez y solo inicializa el backfitting, asi
        # que un bandwidth amplio no cuesta precision -- el resultado final de cada
        # variable lo determina su propio bandwidth (bw_bounds) en las iteraciones
        # que siguen.
        init_multi_bw = float(n_total)
        logger.info("Bandwidth semilla (init_multi, modelo con las 9 variables + intercepto): %d", n_total)

        # fixed=False aca tambien: bw_bounds viene de una busqueda adaptativa
        # (cantidad de vecinos), no de distancia en grados -- ver nota extensa al
        # principio del archivo (primer incidente). El fit en si corre en un
        # proceso aparte para poder mostrar progreso mientras corre (heartbeat)
        # en vez de bloquearse en silencio -- ver run_full_fit_with_progress.
        full_fit_timeout_seconds = args.full_fit_timeout_min * 60
        fit_result = run_full_fit_with_progress(
            coords_full, y, X_scaled, bw_bounds, init_multi_bw, args.max_iter_multi,
            PTNA_QUALITY_COLUMNS, df["h3_index"].values, full_fit_timeout_seconds, logger,
        )

        fit_elapsed = time.perf_counter() - t_fit0
        logger.info("Fit sobre el dataset completo OK en %.1f s.", fit_elapsed)

        feature_names = ["intercept"] + PTNA_QUALITY_COLUMNS
        params = fit_result["params"]
        predy = fit_result["predy"]
        bandwidths_full = fit_result["bandwidths_full"]
        coef_stats = pd.DataFrame(
            {"media": params.mean(axis=0), "min": params.min(axis=0), "max": params.max(axis=0)},
            index=feature_names,
        )
        logger.info("Estadisticos de coeficientes por variable:\n%s", coef_stats.to_string())

        result = {
            "h3_index": df["h3_index"].values,
            "y": y,
            "predy": predy,
            "params": params,
            "feature_names": feature_names,
            "bandwidths_full": bandwidths_full,
            "bandwidths_subsample": bw_sub,
            "bandwidths_rescaled": bw_rescaled,
            "bandwidth_scale_factor": scale_factor,
            "bandwidth_floor": bw_floor,
            "init_multi_bw": init_multi_bw,
            "subsample_step": args.subsample_step,
            "max_iter_multi": args.max_iter_multi,
            "n_obs_full": n_total,
            "n_obs_subsample": len(sub_idx),
            "quality_columns": PTNA_QUALITY_COLUMNS,
            "scaler_mean_": scaler.mean_,
            "scaler_scale_": scaler.scale_,
            "median_imputation": medians.to_dict(),
            "timing_sec": {"bw_search_subsample": bw_search_elapsed, "full_fit": fit_elapsed},
        }

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            pickle.dump(result, f)
        logger.info("Modelo guardado en %s", output_path)

        total_elapsed = time.perf_counter() - t0
        logger.info("Script finalizado OK en %.1f s.", total_elapsed)

    except Exception:
        logger.exception("Fallo en %s", SCRIPT_NAME)
        print(f"\nERROR en {SCRIPT_NAME} -- ver analytics/mgwr/logs/{SCRIPT_NAME}.log para el detalle.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"RESUMEN -- {SCRIPT_NAME} (v1 EXPLORATORIO, sin sentimiento_medio)")
    print("=" * 60)
    print(f"Filas dataset completo: {n_total} | Filas submuestreo (bandwidth search): {len(sub_idx)}")
    print("Kernel: ADAPTATIVO (bandwidth = cantidad de vecinos, no grados -- ver nota al principio del script)")
    print(f"Bandwidth submuestreo (crudo):        {bw_sub.round(4).tolist()}")
    print(f"Bandwidth reescalado por densidad (x{scale_factor:.2f}, piso={bw_floor}): {bw_rescaled.tolist()}")
    print(f"Bandwidth semilla del backfitting (init_multi): {int(init_multi_bw)}")
    print(f"Bandwidth dataset completo (resultante): {bandwidths_full.round(4).tolist()}")
    print(f"Tiempo Sel_BW.search() (submuestreo): {bw_search_elapsed:.1f} s")
    print(f"Tiempo fit dataset completo: {fit_elapsed:.1f} s")
    print("Estadisticos de coeficientes por variable (media / min / max):")
    print(coef_stats.round(4).to_string())
    print(f"Guardado en: {output_path}")
    print(f"Tiempo total: {total_elapsed:.1f} s")
    print("=" * 60)


if __name__ == "__main__":
    main()
