from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


GPS_JS = r'''
const GPS_KEY = "__time_tye_gps_watch_v2__";

export default function(component) {
  const { data, setStateValue } = component;

  const active = Boolean(data?.active);
  const intervalMs = Math.max(
    Number(data?.interval_ms) || 5000,
    1000
  );

  /*
   * Estado persistente no window.
   *
   * Isso é importante porque o Streamlit pode reconstruir
   * o componente durante uma execução.
   */
  if (!window[GPS_KEY]) {
    window[GPS_KEY] = {
      watchId: null,
      active: false,
      lastSent: 0,
      lastPositionTimestamp: 0,

      wakeLock: null,

      visibilityHandler: null,
      onlineHandler: null,
      pageShowHandler: null,

      queue: [],

      startedAt: null,
      sessionId: null,
    };
  }

  const gps = window[GPS_KEY];

  /*
   * ---------------------------------------------------------
   * CONFIGURAÇÃO
   * ---------------------------------------------------------
   */

  const STORAGE_KEY = "__time_tye_gps_queue_v2__";
  const MAX_QUEUE_SIZE = 500;

  /*
   * ---------------------------------------------------------
   * STORAGE
   * ---------------------------------------------------------
   */

  function loadQueue() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);

      if (!raw) {
        gps.queue = [];
        return;
      }

      const parsed = JSON.parse(raw);

      if (Array.isArray(parsed)) {
        gps.queue = parsed;
      } else {
        gps.queue = [];
      }

    } catch (err) {
      console.warn("Time Tye GPS: erro ao carregar fila:", err);
      gps.queue = [];
    }
  }

  function saveQueue() {
    try {
      /*
       * Mantém somente os últimos pontos para evitar
       * crescimento infinito do localStorage.
       */
      if (gps.queue.length > MAX_QUEUE_SIZE) {
        gps.queue = gps.queue.slice(-MAX_QUEUE_SIZE);
      }

      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(gps.queue)
      );

    } catch (err) {
      console.warn("Time Tye GPS: erro ao salvar fila:", err);
    }
  }

  function clearQueue() {
    gps.queue = [];

    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      // ignore
    }
  }

  /*
   * ---------------------------------------------------------
   * PUBLICAÇÃO
   * ---------------------------------------------------------
   */

  function publishState(location, error = null) {
    if (location) {
      setStateValue("location", location);
    }

    setStateValue("error", error);
  }

  /*
   * ---------------------------------------------------------
   * WAKE LOCK
   * ---------------------------------------------------------
   *
   * O Wake Lock mantém a tela acordada quando permitido.
   * Ele NÃO é um mecanismo de GPS em background.
   */

  async function requestWakeLock() {
    if (!gps.active) return;

    if (!("wakeLock" in navigator)) {
      return;
    }

    /*
     * Wake Lock só pode ser solicitado quando a página
     * está visível.
     */
    if (document.visibilityState !== "visible") {
      return;
    }

    try {
      if (gps.wakeLock) {
        return;
      }

      gps.wakeLock =
        await navigator.wakeLock.request("screen");

      gps.wakeLock.addEventListener(
        "release",
        () => {
          gps.wakeLock = null;

          /*
           * Se a página continuar visível, tenta recuperar
           * o Wake Lock depois de uma pequena espera.
           */
          if (
            gps.active &&
            document.visibilityState === "visible"
          ) {
            setTimeout(() => {
              requestWakeLock();
            }, 1000);
          }
        },
        { once: true }
      );

    } catch (err) {
      console.warn(
        "Time Tye GPS: Wake Lock indisponível:",
        err
      );
    }
  }

  function releaseWakeLock() {
    if (!gps.wakeLock) {
      return;
    }

    try {
      gps.wakeLock.release();
    } catch (err) {
      // ignore
    }

    gps.wakeLock = null;
  }

  /*
   * ---------------------------------------------------------
   * FILA LOCAL
   * ---------------------------------------------------------
   */

  function addToQueue(location) {
    gps.queue.push(location);

    if (gps.queue.length > MAX_QUEUE_SIZE) {
      gps.queue.shift();
    }

    saveQueue();
  }

  /*
   * Envia novamente o último ponto conhecido.
   *
   * Isso não envia "GPS do passado" como se fosse novo;
   * apenas permite que o Python receba novamente o último
   * ponto quando o componente voltar.
   */

  function republishLastKnownLocation() {
    if (!gps.active) {
      return;
    }

    if (!gps.queue.length) {
      return;
    }

    const last =
      gps.queue[gps.queue.length - 1];

    if (!last) {
      return;
    }

    setStateValue("location", last);
  }

  /*
   * ---------------------------------------------------------
   * GPS
   * ---------------------------------------------------------
   */

  function publishLocation(position) {
    if (!gps.active) {
      return;
    }

    const now = Date.now();

    const c = position.coords;

    /*
     * Ignora posições sem coordenadas válidas.
     */
    if (
      typeof c.latitude !== "number" ||
      typeof c.longitude !== "number"
    ) {
      return;
    }

    const timestamp =
      Number(position.timestamp) || now;

    /*
     * Evita receber exatamente a mesma posição várias vezes.
     */
    if (
      gps.lastPositionTimestamp &&
      timestamp <= gps.lastPositionTimestamp
    ) {
      return;
    }

    gps.lastPositionTimestamp = timestamp;

    const location = {
      latitude: c.latitude,
      longitude: c.longitude,

      altitude:
        c.altitude !== null &&
        c.altitude !== undefined
          ? c.altitude
          : null,

      altitudeAccuracy:
        c.altitudeAccuracy !== null &&
        c.altitudeAccuracy !== undefined
          ? c.altitudeAccuracy
          : null,

      accuracy:
        c.accuracy !== null &&
        c.accuracy !== undefined
          ? c.accuracy
          : null,

      heading:
        c.heading !== null &&
        c.heading !== undefined
          ? c.heading
          : null,

      speed:
        c.speed !== null &&
        c.speed !== undefined
          ? c.speed
          : null,

      timestamp_ms: timestamp,
    };

    /*
     * SEMPRE salva primeiro.
     *
     * Isso é importante: se o intervalo configurado
     * impedir o envio imediato ao Streamlit, o ponto
     * continua protegido localmente.
     */
    addToQueue(location);

    /*
     * Controle de frequência de envio ao Streamlit.
     */
    if (
      gps.lastSent &&
      now - gps.lastSent < intervalMs
    ) {
      return;
    }

    gps.lastSent = now;

    publishState(location, null);
  }

  function publishError(error) {
    if (!gps.active) {
      return;
    }

    setStateValue("error", {
      code: error?.code ?? 0,
      message:
        error?.message ||
        "Não foi possível obter a localização.",
    });
  }

  /*
   * ---------------------------------------------------------
   * WATCH POSITION
   * ---------------------------------------------------------
   */

  function createWatch() {
    if (!gps.active) {
      return;
    }

    if (!navigator.geolocation) {
      publishError({
        code: 0,
        message:
          "Este navegador não oferece geolocalização.",
      });

      return;
    }

    if (gps.watchId !== null) {
      return;
    }

    try {
      gps.watchId =
        navigator.geolocation.watchPosition(
          publishLocation,
          publishError,
          {
            enableHighAccuracy: true,

            /*
             * Aceita uma posição recente, mas não muito antiga.
             */
            maximumAge: 2000,

            /*
             * Dá tempo para o GPS obter uma posição.
             */
            timeout: 20000,
          }
        );

    } catch (err) {
      console.error(
        "Time Tye GPS: erro ao iniciar watchPosition:",
        err
      );

      publishError({
        code: 0,
        message:
          "Erro ao iniciar o rastreamento GPS.",
      });
    }
  }

  function destroyWatch() {
    if (
      gps.watchId !== null &&
      navigator.geolocation
    ) {
      try {
        navigator.geolocation.clearWatch(
          gps.watchId
        );
      } catch (err) {
        // ignore
      }
    }

    gps.watchId = null;
  }

  /*
   * ---------------------------------------------------------
   * START / STOP
   * ---------------------------------------------------------
   */

  function start() {
    if (gps.active) {
      /*
       * O componente pode ser executado novamente
       * pelo Streamlit. Não cria outro watcher.
       */
      requestWakeLock();
      createWatch();
      republishLastKnownLocation();

      return;
    }

    gps.active = true;

    gps.startedAt = Date.now();

    /*
     * Identificador da sessão do navegador.
     */
    gps.sessionId =
      String(Date.now()) +
      "-" +
      Math.random()
        .toString(36)
        .slice(2);

    /*
     * Carrega pontos que eventualmente tenham ficado
     * armazenados de uma execução anterior.
     */
    loadQueue();

    requestWakeLock();

    createWatch();

    /*
     * Se já houver posição conhecida, publica.
     */
    republishLastKnownLocation();
  }

  function stop() {
    gps.active = false;

    destroyWatch();

    releaseWakeLock();

    gps.startedAt = null;
    gps.sessionId = null;

    /*
     * NÃO apagamos automaticamente a fila aqui.
     *
     * Isso permite que o último ponto permaneça
     * disponível até o navegador limpar o storage.
     */
  }

  /*
   * ---------------------------------------------------------
   * VISIBILITY CHANGE
   * ---------------------------------------------------------
   *
   * Quando a página volta para visible:
   *
   * 1. tenta recuperar Wake Lock;
   * 2. verifica o watcher;
   * 3. republica a última posição;
   * 4. garante que o GPS esteja novamente ativo.
   */

  if (!gps.visibilityHandler) {
    gps.visibilityHandler = () => {

      if (!gps.active) {
        return;
      }

      if (
        document.visibilityState === "visible"
      ) {
        console.log(
          "Time Tye GPS: página voltou ao primeiro plano."
        );

        requestWakeLock();

        /*
         * Alguns navegadores continuam com o watcher.
         * Outros podem ter perdido o acompanhamento.
         */
        if (gps.watchId === null) {
          createWatch();
        }

        /*
         * Recupera imediatamente o último ponto.
         */
        republishLastKnownLocation();
      }
    };

    document.addEventListener(
      "visibilitychange",
      gps.visibilityHandler
    );
  }

  /*
   * ---------------------------------------------------------
   * PAGE SHOW
   * ---------------------------------------------------------
   *
   * Ajuda em casos onde a página retorna através
   * do histórico/cache do navegador.
   */

  if (!gps.pageShowHandler) {
    gps.pageShowHandler = () => {

      if (!gps.active) {
        return;
      }

      console.log(
        "Time Tye GPS: pageshow."
      );

      if (
        document.visibilityState === "visible"
      ) {
        requestWakeLock();

        if (gps.watchId === null) {
          createWatch();
        }

        republishLastKnownLocation();
      }
    };

    window.addEventListener(
      "pageshow",
      gps.pageShowHandler
    );
  }

  /*
   * ---------------------------------------------------------
   * ONLINE
   * ---------------------------------------------------------
   *
   * Quando a conexão volta, republica o último ponto.
   */

  if (!gps.onlineHandler) {
    gps.onlineHandler = () => {

      if (!gps.active) {
        return;
      }

      console.log(
        "Time Tye GPS: conexão voltou."
      );

      republishLastKnownLocation();
    };

    window.addEventListener(
      "online",
      gps.onlineHandler
    );
  }

  /*
   * ---------------------------------------------------------
   * EXECUÇÃO
   * ---------------------------------------------------------
   */

  if (active) {
    start();
  } else {
    if (gps.active) {
      stop();
    }
  }

  /*
   * ---------------------------------------------------------
   * CLEANUP
   * ---------------------------------------------------------
   *
   * IMPORTANTE:
   * Não removemos os listeners globais aqui porque
   * o componente pode ser reconstruído pelo Streamlit.
   *
   * O watcher é encerrado quando active=false.
   */

  return () => {
    /*
     * Não desligamos o GPS aqui.
     *
     * O Streamlit pode desmontar/reconstruir o componente
     * durante uma execução sem que a corrida tenha acabado.
     *
     * O controle real é feito por data.active.
     */
  };
}
'''


_gps_component = st.components.v2.component(
    "time_tye_browser_gps_v2",
    html="""
    <div
        aria-hidden="true"
        style="
            height:1px;
            width:1px;
            overflow:hidden;
        "
    ></div>
    """,
    js=GPS_JS,
    isolate_styles=False,
)


def get_browser_location(
    key: str,
    interval_ms: int = 5000,
    active: bool = True,
) -> dict:
    """
    Obtém a posição GPS do navegador.

    Mantém a mesma interface da versão anterior
    para não exigir alterações no restante do aplicativo.
    """

    result = _gps_component(
        key=key,
        data={
            "active": active,
            "interval_ms": interval_ms,
        },
        default={
            "location": None,
            "error": None,
        },
        on_location_change=lambda: None,
        on_error_change=lambda: None,
    )

    location = getattr(
        result,
        "location",
        None,
    )

    error = getattr(
        result,
        "error",
        None,
    )

    if not location:
        return {
            "available": False,
            "error": error,
        }

    timestamp_ms = float(
        location.get(
            "timestamp_ms",
            0,
        )
    )

    return {
        "available": True,

        "timestamp": datetime.fromtimestamp(
            timestamp_ms / 1000,
            tz=timezone.utc,
        ).isoformat(),

        "latitude": float(
            location["latitude"]
        ),

        "longitude": float(
            location["longitude"]
        ),

        "altitude": (
            float(location["altitude"])
            if location.get("altitude") is not None
            else None
        ),

        "speed": (
            float(location["speed"])
            if location.get("speed") is not None
            else None
        ),

        "accuracy": (
            float(location["accuracy"])
            if location.get("accuracy") is not None
            else None
        ),
    }
