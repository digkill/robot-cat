# Git Workflow

Базовая схема веток для проекта:

- `main`
  Только стабильные, продовые коммиты.
- `develop`
  Интеграционная ветка для следующего релиза.
- `feature/<short-name>`
  Рабочие ветки под отдельные задачи.
- `hotfix/<short-name>`
  Срочные исправления для `main`.
- `release/<version>`
  Подготовка релиза перед вливанием в `main`.

## Правила работы

1. Новые задачи начинаются от `develop`.

```bash
git checkout develop
git pull
git checkout -b feature/<short-name>
```

2. После завершения задачи:

- push ветки `feature/...`
- pull request в `develop`

3. Когда `develop` стабилен:

```bash
git checkout develop
git pull
git checkout -b release/<version>
```

Потом:

- финальные правки
- merge `release/<version>` в `main`
- tag вида `vX.Y.Z`
- merge обратно в `develop`

4. Срочный фикс прода:

```bash
git checkout main
git pull
git checkout -b hotfix/<short-name>
```

После фикса:

- merge в `main`
- новый tag
- merge в `develop`

## Теги

Использовать semver:

- `v0.1.0`
- `v0.1.1`
- `v0.2.0`

Тег `dev` допустим как временный snapshot, но не как постоянная схема релизов.

## Что уже есть в проекте

- `main` — базовая стабильная ветка
- `develop` — интеграционная ветка
- `dev` — временный development tag

## Рекомендуемая практика коммитов

- один PR = одна задача
- короткие, предметные коммиты
- не пушить напрямую в `main`
- в `develop` лучше попадать через PR, а не прямым push
