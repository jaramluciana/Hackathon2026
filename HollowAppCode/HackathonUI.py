import flet as ft
import pyodbc

# ---------- THEME ----------
BG_TOP = "#0b0d12"
BG_BOTTOM = "#1a1f2b"
CARD_BG = "#10131a"
ACCENT = "#c9b37e"
ACCENT_DIM = "#6e6246"
TEXT = "#d8d4c8"
TEXT_DIM = "#8a8678"
ERROR = "#b5524a"
SUCCESS = "#7fa37a"
FONT = "Georgia"


# ---------- DATABASE ----------
def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=ResidentInfors;"
        "Trusted_Connection=yes;"
    )


def check_login(user_id, password):
    """True = correct, False = wrong, None = database error."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM Account WHERE UserID = ? AND Password = ?",
            (user_id, password),
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception as ex:
        print("Database error:", ex)
        return None


def create_account(password):
    """Auto-generated ID: one letter + 7 digits (A0000001 ... A9999999, B0000001 ...).
    Returns (status, new_id). status is 'ok' or 'error'."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        for _ in range(5):
            cursor.execute(
                "SELECT MAX(UserID COLLATE Latin1_General_BIN) FROM Account "
                "WHERE UserID COLLATE Latin1_General_BIN "
                "LIKE '[A-Z][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'"
            )
            last_id = cursor.fetchone()[0]

            if last_id:
                letter = last_id[0]
                number = int(last_id[1:]) + 1
                if number > 9999999:
                    letter = chr(ord(letter) + 1)
                    number = 1
                if letter > "Z":
                    conn.close()
                    return "error", None
            else:
                letter, number = "A", 1

            new_id = f"{letter}{number:07d}"

            try:
                cursor.execute(
                    "INSERT INTO Account (UserID, Password) VALUES (?, ?)",
                    (new_id, password),
                )
                conn.commit()
                conn.close()
                return "ok", new_id
            except pyodbc.IntegrityError:
                conn.rollback()

        conn.close()
        return "error", None
    except Exception as ex:
        print("Database error:", ex)
        return "error", None


# ---------- ABYSS LOGO (concentric circles) ----------
def abyss_logo(size=72):
    """Hollow / abyss emblem: outer ring, inner ring, glowing black void."""
    void = ft.Container(
        width=size * 0.36,
        height=size * 0.36,
        border_radius=size,
        bgcolor="#000000",
        border=ft.Border.all(1, ACCENT_DIM),
        shadow=ft.BoxShadow(blur_radius=size * 0.35, spread_radius=1,
                            color="#66c9b37e"),
    )
    middle = ft.Container(
        width=size * 0.68,
        height=size * 0.68,
        border_radius=size,
        border=ft.Border.all(1, ACCENT),
        alignment=ft.Alignment(0, 0),
        content=void,
    )
    return ft.Container(
        width=size,
        height=size,
        border_radius=size,
        border=ft.Border.all(1, ACCENT_DIM),
        alignment=ft.Alignment(0, 0),
        content=middle,
    )


def main(page: ft.Page):
    page.title = "Hollow City"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_TOP

    # ---------- REUSABLE STYLES ----------
    def make_field(label, icon, is_password=False, on_submit=None):
        return ft.TextField(
            label=label,
            prefix_icon=icon,
            password=is_password,
            can_reveal_password=is_password,
            width=320,
            color=TEXT,
            cursor_color=ACCENT,
            bgcolor="#0b0e14",
            border_color=ACCENT_DIM,
            focused_border_color=ACCENT,
            border_radius=2,
            label_style=ft.TextStyle(color=TEXT_DIM, size=12, font_family=FONT),
            text_style=ft.TextStyle(font_family=FONT, size=15),
            on_submit=on_submit,
        )

    def make_button(text, on_click):
        return ft.Button(
            content=ft.Text(text, size=14, font_family=FONT,
                            weight=ft.FontWeight.BOLD),
            width=320,
            height=46,
            on_click=on_click,
            style=ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: ACCENT,
                       ft.ControlState.HOVERED: "#0b0d12"},
                bgcolor={ft.ControlState.DEFAULT: "#00000000",
                         ft.ControlState.HOVERED: ACCENT},
                side=ft.BorderSide(1, ACCENT),
                shape=ft.RoundedRectangleBorder(radius=2),
                animation_duration=250,
            ),
        )

    def make_link(text, on_click):
        return ft.TextButton(
            content=ft.Text(text, size=12, color=TEXT_DIM, font_family=FONT),
            on_click=on_click,
        )

    def divider():
        return ft.Container(width=120, height=1, bgcolor=ACCENT_DIM)

    def glow_on_hover(e):
        hovered = str(e.data).lower() == "true"
        e.control.border = ft.Border.all(1, ACCENT if hovered else ACCENT_DIM)
        e.control.shadow = ft.BoxShadow(
            blur_radius=30 if hovered else 0,
            color="#44c9b37e",
        )
        e.control.update()

    def make_tile(icon, label, on_click):
        return ft.Container(
            width=130,
            height=130,
            bgcolor=CARD_BG,
            border=ft.Border.all(1, ACCENT_DIM),
            border_radius=4,
            alignment=ft.Alignment(0, 0),
            ink=True,
            on_click=on_click,
            on_hover=glow_on_hover,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                [
                    ft.Icon(icon, size=40, color=ACCENT),
                    ft.Text(label, size=11, color=TEXT, font_family=FONT,
                            style=ft.TextStyle(letter_spacing=2),
                            text_align=ft.TextAlign.CENTER),
                ],
                tight=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def make_bell(on_click):
        return ft.Container(
            width=56,
            height=56,
            border_radius=28,
            bgcolor=CARD_BG,
            border=ft.Border.all(1, ACCENT_DIM),
            alignment=ft.Alignment(0, 0),
            ink=True,
            on_click=on_click,
            on_hover=glow_on_hover,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            content=ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, size=26, color=ACCENT),
        )

    def gradient_screen(content):
        return ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
                colors=[BG_TOP, BG_BOTTOM],
            ),
            content=content,
        )

    def wrap_screen(card_content):
        """Centered framed card (used by login / register)."""
        return ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
                colors=[BG_TOP, BG_BOTTOM],
            ),
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=420,
                padding=40,
                bgcolor=CARD_BG,
                border=ft.Border.all(1, ACCENT_DIM),
                border_radius=4,
                shadow=ft.BoxShadow(
                    blur_radius=60, color="#33c9b37e", spread_radius=1,
                ),
                content=card_content,
            ),
        )

    def title_block(title, subtitle):
        return [
            abyss_logo(72),
            ft.Text(title, size=30, color=TEXT, font_family=FONT,
                    weight=ft.FontWeight.BOLD,
                    style=ft.TextStyle(letter_spacing=6)),
            ft.Text(subtitle, size=11, color=TEXT_DIM, font_family=FONT,
                    style=ft.TextStyle(letter_spacing=4)),
            divider(),
            ft.Container(height=10),
        ]

    # ---------- LOGIN FIELDS ----------
    login_user = make_field("USER ID (e.g. A0000001)", ft.Icons.PERSON_OUTLINE,
                            on_submit=lambda e: handle_login(e))
    login_pass = make_field("PASSWORD", ft.Icons.LOCK_OUTLINE,
                            is_password=True,
                            on_submit=lambda e: handle_login(e))
    login_msg = ft.Text("", color=ERROR, size=13, font_family=FONT,
                        text_align=ft.TextAlign.CENTER)

    # ---------- REGISTER FIELDS ----------
    reg_pass = make_field("PASSWORD", ft.Icons.LOCK_OUTLINE, is_password=True)
    reg_confirm = make_field("CONFIRM PASSWORD", ft.Icons.LOCK_OUTLINE,
                             is_password=True,
                             on_submit=lambda e: handle_register(e))
    reg_msg = ft.Text("", color=ERROR, size=13, font_family=FONT,
                      text_align=ft.TextAlign.CENTER)

    # ---------- SCREENS ----------
    def show_login(notice="", prefill=""):
        login_user.value = prefill
        login_pass.value = ""
        login_msg.value = notice
        login_msg.color = SUCCESS if notice else ERROR
        page.controls.clear()
        page.add(
            wrap_screen(
                ft.Column(
                    title_block("HOLLOW CITY", "RESIDENT ACCESS") + [
                        login_user,
                        login_pass,
                        login_msg,
                        ft.Container(height=4),
                        make_button("ENTER", handle_login),
                        make_link("No account? Create one",
                                  lambda e: show_register()),
                    ],
                    tight=True,
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        )
        page.update()

    def show_register():
        reg_pass.value = ""
        reg_confirm.value = ""
        reg_msg.value = ""
        reg_msg.color = ERROR
        page.controls.clear()
        page.add(
            wrap_screen(
                ft.Column(
                    title_block("NEW RESIDENT", "CREATE ACCOUNT") + [
                        ft.Text("Your ID will be assigned automatically.",
                                size=12, color=TEXT_DIM, font_family=FONT,
                                text_align=ft.TextAlign.CENTER),
                        reg_pass,
                        reg_confirm,
                        reg_msg,
                        ft.Container(height=4),
                        make_button("REGISTER", handle_register),
                        make_link("Already have an account? Back to login",
                                  lambda e: show_login()),
                    ],
                    tight=True,
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        )
        page.update()

    def show_home(user_id):
        page.controls.clear()

        top_bar = ft.Row(
            [make_link("LEAVE", lambda e: show_login())],
            alignment=ft.MainAxisAlignment.END,
        )

        center = ft.Column(
            [
                abyss_logo(84),
                ft.Text("HOLLOW CITY", size=30, color=TEXT, font_family=FONT,
                        weight=ft.FontWeight.BOLD,
                        style=ft.TextStyle(letter_spacing=6)),
                ft.Text(f"WELCOME, {user_id.upper()}", size=11, color=TEXT_DIM,
                        font_family=FONT,
                        style=ft.TextStyle(letter_spacing=4)),
                divider(),
                ft.Container(height=20),
                ft.Row(
                    [
                        make_tile(ft.Icons.MEDICAL_SERVICES_OUTLINED, "MEDICAL",
                                  lambda e: show_blank("MEDICAL",
                                                       ft.Icons.MEDICAL_SERVICES_OUTLINED,
                                                       user_id)),
                        make_tile(ft.Icons.VIEW_IN_AR_OUTLINED, "3D MAP",
                                  lambda e: show_blank("3D MAP",
                                                       ft.Icons.VIEW_IN_AR_OUTLINED,
                                                       user_id)),
                        make_tile(ft.Icons.WARNING_AMBER_OUTLINED, "ALERT SYSTEM",
                                  lambda e: show_blank("ALERT SYSTEM",
                                                       ft.Icons.WARNING_AMBER_OUTLINED,
                                                       user_id)),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                    spacing=20,
                    run_spacing=20,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
        )

        bottom = ft.Container(
            padding=ft.Padding.only(bottom=30),
            alignment=ft.Alignment(0, 0),
            content=make_bell(
                lambda e: show_blank("NOTIFICATIONS",
                                     ft.Icons.NOTIFICATIONS_OUTLINED, user_id)
            ),
        )

        page.add(
            gradient_screen(
                ft.Column(
                    [top_bar, center, bottom],
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        )
        page.update()

    def show_blank(title, icon, user_id):
        """Empty placeholder page with a back button."""
        page.controls.clear()
        header = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color=ACCENT,
                    on_click=lambda e: show_home(user_id),
                ),
                ft.Icon(icon, size=22, color=ACCENT),
                ft.Text(title, size=16, color=TEXT, font_family=FONT,
                        weight=ft.FontWeight.BOLD,
                        style=ft.TextStyle(letter_spacing=4)),
            ],
            spacing=10,
        )
        page.add(
            gradient_screen(
                ft.Column(
                    [
                        ft.Container(padding=10, content=header),
                        ft.Container(height=1, bgcolor=ACCENT_DIM),
                        ft.Container(expand=True),  # empty body for now
                    ],
                    expand=True,
                    spacing=0,
                )
            )
        )
        page.update()

    # ---------- LOGIC ----------
    def handle_login(e):
        if not login_user.value or not login_pass.value:
            login_msg.color = ERROR
            login_msg.value = "Please enter both ID and password"
            page.update()
            return

        result = check_login(login_user.value.strip(), login_pass.value)

        if result is None:
            login_msg.color = ERROR
            login_msg.value = "Cannot connect to the database"
        elif result:
            show_home(login_user.value.strip())
            return
        else:
            login_msg.color = ERROR
            login_msg.value = "WRONG PASSWORD OR INVALID ID"
        page.update()

    def handle_register(e):
        pw = reg_pass.value
        confirm = reg_confirm.value

        if not pw or not confirm:
            reg_msg.value = "Please fill in all fields"
        elif len(pw) < 6:
            reg_msg.value = "Password must be at least 6 characters"
        elif pw != confirm:
            reg_msg.value = "Passwords do not match"
        else:
            status, new_id = create_account(pw)
            if status == "ok":
                show_login(f"Account created. Your ID is {new_id}",
                           prefill=new_id)
                return
            reg_msg.value = "Cannot connect to the database"
        page.update()

    show_login()


ft.run(main)