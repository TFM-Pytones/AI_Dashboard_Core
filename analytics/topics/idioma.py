"""Detector de idioma aproximado por palabras frecuentes, sin dependencias.

No busca precision fina: se usa para centrar los embeddings por idioma antes de
agrupar (ver entrenar_topicos.py) y para medir si los temas se agrupan por
idioma en vez de por contenido. Comprobado contra el pais del reseñante de
Booking: el 95 % de los españoles sale 'es', el 96 % de los britanicos 'en',
el 90 % de los italianos 'it' y el 88 % de los franceses 'fr' (el resto
suelen ser reseñas escritas de verdad en otro idioma, sobre todo en ingles).

'sc' agrupa danes, noruego y sueco; 'unk' son textos sin ninguna palabra
reconocible (emojis, nombres propios sueltos).
"""

import re

PALABRAS = {
    "es": "que el en y los del se las por un para con una su al lo como más pero muy todo bien habitación "
          "ubicación personal limpio limpieza cerca playa piscina desayuno estaba había apartamento nada "
          "genial excelente tranquilo buena bueno hay está gracias zona también".split(),
    "en": "the and was to of is it for with very we were great nice clean staff location room good close "
          "beach pool breakfast would stay lovely apartment everything friendly helpful not our there this "
          "had place".split(),
    "de": "der die das und ist war sehr wir mit nicht ein eine für auf zu den im es gut sauber lage personal "
          "zimmer strand frühstück alles schön leider nur auch uns wohnung".split(),
    "fr": "le les et est était très nous un une pour avec pas des du bien propre emplacement personnel "
          "chambre plage petit tout séjour appartement avons vraiment".split(),
    "it": "il le è era molto di un una per con non del della bene pulito posizione personale camera "
          "spiaggia colazione tutto appartamento soggiorno ottima ottimo".split(),
    "pt": "os as é foi muito um uma para com não do da bem limpo localização pessoal quarto praia pequeno "
          "tudo estadia ótima ótimo".split(),
    "nl": "het een en is was zeer erg we wij met niet voor op van goed schoon ligging personeel kamer strand "
          "ontbijt alles mooi appartement".split(),
    "pl": "w na jest było bardzo nie z do się to że czysto lokalizacja personel pokój plaża śniadanie "
          "wszystko apartament polecam".split(),
    "cs": "je byl bylo velmi na se to že čisto lokalita personál pokoj pláž snídaně vše apartmán".split(),
    "ro": "și este fost foarte în la cu nu pentru curat locație personal cameră plajă totul apartament".split(),
    "hu": "az és volt nagyon nem egy is hogy szép tiszta elhelyezkedés személyzet szoba strand reggeli "
          "minden apartman".split(),
    "sc": "og er var meget veldig mycket det et på med til ikke inte jeg vi rent beliggenhed beliggenhet "
          "läge rom rum alt allt lejlighet leilighet".split(),
    # Sin estos, las reseñas de Finlandia, Lituania, Estonia, Letonia e
    # Islandia quedaban como 'unk', no se centraban y acababan agrupadas juntas.
    "fi": "ja on oli ei se että hyvä erittäin kaikki huone asunto sijainti siisti ranta henkilökunta mutta myös kun "
          "olivat meille".split(),
    "et": "ja on oli ei see väga hea kõik tuba korter asukoht puhas rand personal aga ka meil".split(),
    "lt": "ir yra buvo labai geras gera viskas kambarys butas vieta švaru švarus paplūdimys personalas bet taip pat "
          "mums".split(),
    "lv": "un ir bija ļoti labs laba viss istaba dzīvoklis atrašanās vieta tīrs pludmale personāls bet arī mums".split(),
    "is": "og er var mjög góð góður gott allt herbergi íbúð staðsetning hreint strönd starfsfólk en líka við að "
          "ekki það".split(),
}

_INDICE: dict[str, list[str]] = {}
for _lengua, _palabras in PALABRAS.items():
    for _p in _palabras:
        _INDICE.setdefault(_p, []).append(_lengua)
_ORDEN = list(PALABRAS)
_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def detectar(texto: str) -> str:
    """Devuelve el codigo del idioma con mas palabras reconocidas; en caso de
    empate gana el primero de PALABRAS (los mas frecuentes del corpus)."""
    if re.search(r"[Ѐ-ӿ]", texto):
        return "ru"
    if re.search(r"[Ͱ-Ͽ]", texto):
        return "el"
    puntos: dict[str, int] = {}
    for token in _TOKEN.findall(texto.lower()):
        for lengua in _INDICE.get(token, ()):
            puntos[lengua] = puntos.get(lengua, 0) + 1
    if not puntos:
        return "unk"
    return max(puntos, key=lambda l: (puntos[l], -_ORDEN.index(l)))
