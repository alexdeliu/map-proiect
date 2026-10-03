# [Titlul proiectului]

Proiect individual la disciplina Metode avansate de programare, anul universitar 2026-2027.

## Autor

- **Nume:** [Nume Prenume]
- **Grupa:** [grupa]
- **Marca:** [marca]
- **Tema:** [numarul temei] - [titlul temei]

## Descriere

[Doua-trei propozitii despre ce face aplicatia si ce problema rezolva.]

## Tehnologii

Python 3.13 cu Flask

## Rulare

```
docker build -t map-proiect .
docker run -d -p 8080:8080 map-proiect
```

Aplicatia asculta pe portul 8080. Verificati:

```
curl http://localhost:8080/health
curl http://localhost:8080/version
```

## Testare

```
pip install -r requirements.txt pytest pytest-cov
python -m pytest --cov=src
```

## Rutele implementate

| Ruta | Metoda | Descriere |
|---|---|---|
| `/health` | GET | Starea serviciului |
| `/version` | GET | Versiunea si commit-ul din care a fost construita imaginea |
| `/` | GET | Pagina de prezentare |
| `/reset` | POST | Goleste datele din memorie |
| [ruta temei] | [metoda] | [descriere] |

## Decizii de implementare

[Doua-trei decizii tehnice pe care le-ati luat si motivul fiecareia.]