# Facebook BDays

<!-- TABLE OF CONTENTS -->

## Table of Contents

- [Projektről](#about-the-project)
  - [Használt eszközök](#built-with)
- [Szerver telepítése](#getting-started)
  - [Szükséges programok](#szükséges-programok)
  - [Telepítés](#Telepítés)
  - [Production build](#production-build)
- [Licensz](#licensz)
- [Kapcsolat](#Kapcsolat)

<!-- Projektről -->

## Projektről

Facebook törölte az ismerősök születésnapjainak exportálását külső naptárba,
bár sok embernek hasznos volt a funkció.

A megoldást az [fb2cal](https://github.com/mobeigi/fb2cal) python-szkript jelentette,
azonban egy nem-hozzáértőnek nehéz telepíteni az eszköz futtatásához szükséges szoftvereket és könyvtárakat.

Ennek a projektnek a célja, hogy egy egyszerű webes felületen lehessen kiexportálni az ismerősök születésnapjait.

### Használt eszközök

- [fb2cal](https://github.com/mobeigi/fb2cal)
- [Flask](https://palletsprojects.com/p/flask/)
- [Vue](https://vuejs.org/)
- [Vuetify](https://vuetifyjs.com)

<!-- Szerver telepítése -->

## Szerver telepítése

Így lehet felállítani egy fejlesztői szervert.

### Szükséges programok

- [Pipenv](https://pipenv-fork.readthedocs.io/en/latest/)

- [Npm](https://nodejs.org)

- Yarn

```
npm i -g yarn
```

### Telepítés

1. Klónozd le
   a repot

```sh
git clone https:://github.com/pmihaly/facebook-bdays.git
```

1. Lépj be a virtuális környezetbe

```
pipenv facebook-bdays
```

1. Telepítsd az NPM csomagokat

```sh
yarn install
```

4. Indítsd el a szervert és a klienst

```
yarn dev
```

### Production build

1. `.html`, `.js` és `.css` fájlok előállítása:

```
yarn build
```

2. [Production szerver előállítása](https://flask.palletsprojects.com/en/1.1.x/tutorial/deploy/)

<!-- Licensz -->

## Licensz

GNU GPLv3 alatt licenszelve, lásd LICENSE.

<!-- Kapcsolat -->

## Kapcsolat

Papp Mihály - [pmihaly](https://github.com/pmihaly/) - papp.misi@protonmail.com

Projekt Link: [https://github.com/pmihaly/facebook-bdays](https://github.com/pmihaly/facebook-bdays)
