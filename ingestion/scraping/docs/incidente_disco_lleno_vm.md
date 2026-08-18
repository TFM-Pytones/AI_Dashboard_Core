# Incidente: disco lleno en la VM y reseñas huérfanas resultantes

**Fecha:** 18 de agosto de 2026
**Fuente:** Corrida de `run_continuous.py` en la VM Azure (`mv-orquestador-tfm`)

## Qué pasó

Durante una corrida nocturna/diurna extendida con `MAX_ESTABLISHMENTS_PER_RUN = 100`, el scraper falló con el siguiente error de Selenium:

```
Message: invalid session id: session deleted as the browser has closed the connection
from disconnected: not connected to DevTools
```

## Diagnóstico

Se investigaron dos hipótesis en orden:

1. **Falta de RAM (OOM-Killer)** — descartada. `sudo dmesg | grep -i "oom\|killed process"` no devolvió ningún resultado.
2. **Disco lleno** — confirmada. El propio mensaje de bienvenida de SSH mostraba:
   ```
   Usage of /:   99.8% of 28.02GB
   => / is using 99.8% of 28.02GB
   ```
   Con el disco casi al 100%, Chrome no pudo escribir sus archivos temporales de sesión (caché, perfil de usuario), provocando el cierre abrupto del navegador a mitad de la extracción de un establecimiento.

## Causa raíz del disco lleno

El entorno virtual (`.venv`) de la VM tenía instaladas librerías pesadas de Machine Learning (`torch`, `transformers`, dependencias de NVIDIA/CUDA, `triton`) que **no son necesarias para el scraper de Booking** — pertenecen a otras partes del proyecto (análisis de sentimiento). Estas librerías, sumadas, ocupaban varios GB:

| Elemento | Tamaño |
|---|---|
| `triton` (compilador de kernels GPU, dependencia huérfana de torch) | 594 MB |
| Paquetes `nvidia-*` (CUDA runtime, cuBLAS, cuFFT, etc.) | ~200 MB |
| `.venv` total antes de la limpieza | 4.9 GB |
| `.venv` total después de la limpieza | ~1.5 GB (aprox.) |

Se liberaron aproximadamente **3.4 GB** desinstalando estas librerías innecesarias para scraping, sin afectar las dependencias reales del proyecto compartidas por el equipo (`scipy`, `sklearn`, `pyogrio`, `rasterio`, `pandas`, `pyarrow` — usadas por otros módulos del proyecto y por el propio scraper, respectivamente, y por lo tanto no se tocaron).

## Consecuencia en los datos: reseñas huérfanas

Como resultado de la interrupción abrupta de Chrome a mitad de proceso, se detectaron **30 reseñas sin establecimiento correspondiente** al validar la corrida (`validate_booking_data.py`):

```
[ERROR] 30 reseña(s) sin establecimiento correspondiente
```

### Hipótesis de origen
El guardado incremental (`save_and_upload()`) sube establecimiento y reseñas en la misma operación, pero un cierre abrupto de Chrome en el momento exacto de la extracción pudo dejar un archivo de reseñas en Blob Storage sin su correspondiente archivo de establecimiento (o con inconsistencia de timestamp entre ambos).

### Impacto real: nulo en la capa Silver
El modelo dbt `silver_booking_reviews.sql` ya realiza un `INNER JOIN` contra los establecimientos válidos deduplicados:
```sql
FROM deduplicated r
INNER JOIN valid_establishments e
    ON r.establishment_id = e.establishment_id
```
Esto **filtra automáticamente** cualquier reseña huérfana antes de que llegue a Silver — no requirió intervención manual ni afectó la calidad de los datos limpios finales. Las 30 filas quedan descartadas de forma transparente en la transformación Bronce → Silver.

### Decisión tomada
No se realizó limpieza manual de las reseñas huérfanas en Bronce (append-only por diseño, ver convención ya establecida del proyecto) — el filtrado automático en Silver es suficiente y consistente con el resto del pipeline.

## Prevención hacia adelante

1. **Monitorear espacio en disco de la VM periódicamente**, no solo memoria RAM — ambos recursos son limitados en `mv-orquestador-tfm` (29 GB disco, ~842 MiB RAM).
2. **No instalar `requirements.txt` completo en la VM** — usar instalación puntual de las librerías que el scraper realmente necesita (`selenium`, `beautifulsoup4`, `webdriver-manager`, `pandas`, `azure-storage-blob`, `requests`, `python-dotenv`, `pyarrow`).
3. Si en algún momento se necesita instalar `requirements.txt` completo en la VM (por ejemplo, para probar otro módulo del proyecto ahí), **desinstalar `torch`/`transformers`/`triton` inmediatamente después** si no se van a usar de forma sostenida.

## Comandos de diagnóstico útiles (referencia rápida)

```bash
# Confirmar espacio en disco
df -h /

# Buscar qué ocupa más espacio dentro del proyecto
du -sh ~/AI_Dashboard_Core/.venv/lib/python*/site-packages/* 2>/dev/null | sort -rh | head -10

# Descartar/confirmar OOM-Killer como causa
sudo dmesg | grep -i "oom\|killed process" | tail -20

# Liberar espacio de forma segura (no afecta dependencias de otros módulos)
pip uninstall triton nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 \
    nvidia-cuda-runtime-cu12 nvidia-cufft-cu12 nvidia-cufile-cu12 nvidia-curand-cu12 \
    nvidia-cusparse-cu12 nvidia-cusparselt-cu12 nvidia-nccl-cu12 nvidia-nvjitlink-cu12 \
    nvidia-nvshmem-cu12 nvidia-nvtx-cu12 -y
```
