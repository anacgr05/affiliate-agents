"""Script de backfill: persiste posts.json no PostgreSQL e dispara geração de imagem.

Uso:
    PYTHONPATH=. python backend/backfill.py           # todos os posts
    PYTHONPATH=. python backend/backfill.py --dry-run # apenas lista, não dispara
"""

import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from services.post_repository import ensure_tables_exist, save_post
from backend.celery_app import celery_app


def run_backfill(dry_run: bool = False) -> None:
    posts_file = os.path.join(_PROJECT_ROOT, "data", "posts.json")

    if not os.path.exists(posts_file):
        print(f"❌ {posts_file} não encontrado")
        sys.exit(1)

    with open(posts_file, encoding="utf-8") as fh:
        posts: list[dict] = json.load(fh)

    print(f"📂 {len(posts)} post(s) encontrado(s) em posts.json")

    if not dry_run:
        ensure_tables_exist()

    dispatched: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for post in posts:
        slug: str = post.get("slug", "sem-slug")
        title: str = post.get("title", "")
        prompt: str = (
            post.get("hero", {}).get("image_prompt")  # type: ignore[union-attr]
            or title
        )

        if dry_run:
            print(f"  [dry-run] {slug}")
            skipped.append(slug)
            continue

        try:
            post_id = save_post(post)
            celery_app.send_task(
                "backend.worker.generate_image_task",
                args=[post_id, prompt],
            )
            print(f"  ✅ {slug}  →  post_id={post_id}  (job disparado)")
            dispatched.append(slug)
        except Exception as exc:
            print(f"  ❌ {slug}  →  {exc}")
            failed.append(slug)

    print(f"\n{'='*50}")
    print(f"Disparados : {len(dispatched)}")
    print(f"Falhas     : {len(failed)}")
    if dry_run:
        print(f"Dry-run    : {len(skipped)} (nada foi alterado)")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_backfill(dry_run=dry_run)
