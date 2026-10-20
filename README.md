# Gestiune de inventar

Proiect individual la disciplina Metode avansate de programare, anul universitar 2026-2027.

## Autor

- **Nume:** Deliu Alexandru-Darius
- **Grupa:** 1.1
- **Marca:** 715679
- **Tema:** 4 - Gestiune de inventar

## Descriere

O aplicatie web care gestioneaza un depozit de produse. Tine evidenta stocului curent exclusiv pe baza miscarilor de intrare si de iesire si semnaleaza automat produsele a caror cantitate a scazut sub pragul minim setat.

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
| `/products` | POST | Adauga un produs nou in inventar |
| `/products` | GET | Listeaza produsele |
| `/products/{id}` | GET | Intoarce produsul si stocul curent |
| `/movements` | POST | Inregistreaza o miscare de stoc in sau out |
| `/stats` | GET | Ofera statistici despre stocul total si produsele sub prag |

## Decizii de implementare

Pentru moment, datele sunt stocate in memorie folosind dictionare si liste in Python. Stocul curent nu este o valoare salvata, ci este calculat dinamic la fiecare interogare pe baza istoricului de miscari.