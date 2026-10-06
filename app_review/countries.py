"""Apple App Store storefront codes.

These are the two-letter codes Apple accepts on itunes.apple.com.
Reviews belong to a storefront, so each code is a separate review list.
"""

STOREFRONTS: tuple[str, ...] = tuple(
    """
    ae ag ai al am ao ar at au az bb be bf bg bh bj bm bn bo br bs bt bw by bz
    ca cg ch ci cl cm cn co cr cv cy cz de dk dm do dz ec ee eg es fi fj fm fr
    ga gb gd ge gh gm gr gt gw gy hk hn hr hu id ie il in is it jm jo jp ke kg
    kh kn kr kw ky kz la lb lc lk lr lt lu lv md mg mk ml mn mo mr ms mt mu mw
    mx my mz na ne ng ni nl no np nz om pa pe pg ph pk pl pt pw py qa ro rs ru
    rw sa sb sc se sg si sk sl sn sr st sv sz tc td th tj tm tn tr tt tw tz ua
    ug us uy uz vc ve vg vn vu ws ye za zm zw
    """.split()
)
