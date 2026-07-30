import time
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AgrocabildoClient")

class AgrocabildoAPIClient:
    """
    Cliente Python para la API de datos meteorológicos de Cabildo de Tenerife (Agrocabildo).
    Cumple con las especificaciones del Manual v2.0.0 y respeta el límite de 10 peticiones/min.
    """
    BASE_URL = "https://datos.tenerife.es/api/meteo/latest"

    def __init__(self, min_request_interval: float = 6.5, max_retries: int = 3):
        """
        :param min_request_interval: Intervalo mínimo en segundos entre peticiones HTTP (defecto 6.5s => < 10 req/min).
        :param max_retries: Reintentos en caso de Error 429 o fallos temporales.
        """
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.last_request_time = 0.0

    def _wait_rate_limit(self):
        """Asegura que respetamos la cuota máxima de 10 peticiones por minuto."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_duration = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: esperando {sleep_duration:.2f} segundos...")
            time.sleep(sleep_duration)
        self.last_request_time = time.time()

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Realiza una petición GET con rate-limiting y reintentos automáticos."""
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            self._wait_rate_limit()
            try:
                logger.info(f"GET {url}")
                # Timeout de 60 segundos por si el servidor es lento o está cargado
                response = requests.get(url, params=params, timeout=60)
                
                if response.status_code == 429:
                    wait_time = attempt * 20
                    logger.warning(f"Rate limit excedido (429). Reintentando en {wait_time}s (Intento {attempt}/{max_retries})...")
                    time.sleep(wait_time)
                    continue

                if response.status_code == 404:
                    logger.info(f"Respuesta 404 (Fin de datos o sin registros): {url}")
                    return None

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                wait_time = attempt * 15 # Esperar progresivamente más tiempo para dar margen al servidor para recuperarse
                logger.error(f"Error en GET {url}: {e}. Reintentando en {wait_time}s (Intento {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(wait_time)
                else:
                    raise e

    def get_stations(self, station_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Obtiene el listado completo de estaciones o la información de una única estación."""
        url = f"{self.BASE_URL}/stations"
        params = {"id_weatherstation": station_id} if station_id is not None else None
        data = self._get(url, params=params)
        if data and isinstance(data, dict) and "stations" in data:
            return data["stations"]
        return []

    def get_station_sensors(self, station_id: int) -> List[Dict[str, Any]]:
        """Obtiene la lista de sensores e instrumentos disponibles en una estación específica."""
        url = f"{self.BASE_URL}/stations/{station_id}/sensors"
        data = self._get(url)
        if not data:
            return []
        
        # Estructura devuelta según manual: {"stations": [{"id_weatherstation": X, "sensors": [...]}]}
        if isinstance(data, dict) and "stations" in data:
            stations = data["stations"]
            if len(stations) > 0 and "sensors" in stations[0]:
                return stations[0]["sensors"]
        elif isinstance(data, list):
            return data
        return []

    def get_raw_readings(self, station_id: int, sensor_id: int, date_from: str, date_to: str, page: int = 1) -> Optional[Dict[str, Any]]:
        """
        Consulta las lecturas de un sensor de estación en un rango de fechas (formato AAAA-MM-DD).
        Cada página contiene hasta 10 días de registros.
        """
        url = f"{self.BASE_URL}/readings/station/{station_id}/sensor/{sensor_id}/from/{date_from}/to/{date_to}/{page}"
        return self._get(url)

    def extract_hourly_readings(self, station_id: int, sensor_id: int, date_from: str, date_to: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        Extrae todas las lecturas disponibles sin filtrar por hora en punto.
        """
        hourly_records = []
        
        for page in range(1, max_pages + 1):
            raw_data = self.get_raw_readings(station_id, sensor_id, date_from, date_to, page=page)
            if not raw_data:
                break
            
            parsed_count = 0
            # Parsear estructura 'readings' o 'summarized'
            readings_data = None
            if isinstance(raw_data, dict):
                readings_data = raw_data.get("readings") or raw_data.get("summarized")
            
            if readings_data and isinstance(readings_data, dict):
                sensors = readings_data.get("sensors", [])
                for sensor in sensors:
                    sensor_resp_id = sensor.get("id_weatherstationsensor", sensor_id)
                    
                    # Puede venir en 'values' directamente o dentro de 'dates'
                    entries = sensor.get("values") or []
                    if not entries and "dates" in sensor:
                        for d_entry in sensor.get("dates", []):
                            entries.extend(d_entry.get("values", []))
 
                    for val in entries:
                        obs_date_str = val.get("observation_date")
                        if not obs_date_str:
                            continue
                        
                        hourly_records.append({
                            "id_weatherstation": station_id,
                            "id_weatherstationsensor": sensor_resp_id,
                            "timestamp": obs_date_str,
                            "observation_value": val.get("observation_value"),
                            "validated_value": val.get("validated_value"),
                            "mean": val.get("mean"),
                            "is_validated": val.get("is_visual_validated", True)
                        })
                        parsed_count += 1
 
            # Si no hay datos en esta página, detener iteración
            if parsed_count == 0 and page > 1:
                break
                
        logger.info(f"Estación {station_id} | Sensor {sensor_id} -> {len(hourly_records)} lecturas extraídas.")
        return hourly_records

if __name__ == "__main__":
    # Test de conectividad rápido
    client = AgrocabildoAPIClient()
    stations = client.get_stations(station_id=1)
    print("Estación test ID 1:", stations)
