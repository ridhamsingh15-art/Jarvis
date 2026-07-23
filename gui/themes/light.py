"""Light theme preset — clean whites with blue accents."""

from gui.themes.theme import Theme

LIGHT_THEME = Theme(
    name="Light",
    # Backgrounds
    background="#ffffff",
    surface="#f6f8fa",
    surface_alt="#eef1f5",
    sidebar="#f6f8fa",
    # Borders
    border="#d0d7de",
    border_light="#e1e4e8",
    # Text
    text="#1f2328",
    text_secondary="#424a53",
    text_muted="#656d76",
    # Accent
    accent="#0969da",
    accent_hover="#0550ae",
    accent_muted="rgba(9,105,218,0.1)",
    # Bubbles
    user_bubble="#dbeafe",
    bot_bubble="#f6f8fa",
    error_bubble="rgba(207,34,46,0.06)",
    system_bubble="rgba(101,109,118,0.06)",
    # Status
    success="#1a7f37",
    warning="#9a6700",
    error="#cf222e",
    # Input
    input_bg="#ffffff",
    input_border="#d0d7de",
    # Cards
    card_bg="#ffffff",
    card_border="#d0d7de",
    # Misc
    scrollbar_bg="transparent",
    scrollbar_handle="#d0d7de",
    hover_overlay="rgba(31,35,40,0.04)",
    shadow="rgba(31,35,40,0.1)",
)
