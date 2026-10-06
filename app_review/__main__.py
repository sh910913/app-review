import sys

if len(sys.argv) > 1 and sys.argv[1] == "web":
    from app_review.web import main

    raise SystemExit(main(sys.argv[2:]))

from app_review.cli import main

raise SystemExit(main())
