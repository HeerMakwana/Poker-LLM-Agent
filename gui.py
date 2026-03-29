import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from urllib import request

from agent import GeminiPokerAgent, load_api_key


CARD_BASE_URL = "https://raw.githubusercontent.com/hanhaechi/playing-cards/master"
SUIT_MAP = {"s": "spades", "h": "hearts", "d": "diamonds", "c": "clubs"}
RANK_MAP = {
    "A": "A",
    "K": "K",
    "Q": "Q",
    "J": "J",
    "T": "10",
    "10": "10",
    "9": "9",
    "8": "8",
    "7": "7",
    "6": "6",
    "5": "5",
    "4": "4",
    "3": "3",
    "2": "2",
}
POSITIONS_BY_COUNT = {
    2: ["SB/BTN", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "UTG"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "MP", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO"],
    10: ["BTN", "SB", "BB", "UTG", "UTG+1", "UTG+2", "MP", "LJ", "HJ", "CO"],
}


class PokerGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Gemini Poker Table")
        self.geometry("1280x780")
        self.minsize(1120, 720)
        self.configure(bg="#102217")
        self._resize_after_id = None

        self.assets_dir = os.path.join(os.path.dirname(__file__), "assets", "cards")
        os.makedirs(self.assets_dir, exist_ok=True)
        self.card_image_cache = {}

        self.hand_number = 0
        self.my_stack = 1000
        self.pot_size = 0
        self.amount_to_call = 0
        self.community_cards = []
        self.hole_cards = []
        self.play_blind = False
        self.num_players = 2
        self.my_position = "BB"
        self.street_names = ["Pre-flop", "Flop", "Turn", "River"]
        self.current_street = -1
        self.last_opponent_action = "No actions yet."
        self.opponent_history = []
        self.opponent_labels = ["Opponent 1"]
        self.phase = "pre_game"
        self._updating_position_ui = False
        
        # Opponent state tracking
        self.opponent_states = {}  # {opp_name: {"folded": bool, "contributed": amount}}
        self.current_opponent_index = 0
        self.player_has_acted_this_street = False

        self._build_styles()
        self._build_ui()
        self._load_agent()
        self._update_ui_state()
        self.bind("<Configure>", self._on_root_configure)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Panel.TFrame", background="#173a2d")
        style.configure("Main.TFrame", background="#0f2a1f")
        style.configure("Title.TLabel", background="#0f2a1f", foreground="#f6f2cf", font=("Segoe UI", 21, "bold"))
        style.configure("Meta.TLabel", background="#0f2a1f", foreground="#d2eadb", font=("Segoe UI", 11))
        style.configure("CardSlot.TLabel", background="#184333", foreground="#d7efd9", font=("Segoe UI", 10, "bold"), anchor="center")

        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=8)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="Main.TFrame", padding=12)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 10))

        self.title_label = ttk.Label(header, text="Gemini Poker Table", style="Title.TLabel")
        self.title_label.pack(side="left")

        self.status_label = ttk.Label(header, text="", style="Meta.TLabel")
        self.status_label.pack(side="right")

        body = ttk.Frame(root, style="Main.TFrame")
        body.pack(fill="both", expand=True)

        self.table_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)
        self.table_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.controls_wrapper = ttk.Frame(body, style="Panel.TFrame")
        self.controls_wrapper.pack(side="right", fill="y")

        self.controls_canvas = tk.Canvas(
            self.controls_wrapper,
            background="#173a2d",
            highlightthickness=0,
            bd=0,
            width=390,
        )
        self.controls_scrollbar = ttk.Scrollbar(self.controls_wrapper, orient="vertical", command=self.controls_canvas.yview)
        self.controls_canvas.configure(yscrollcommand=self.controls_scrollbar.set)

        self.controls_scrollbar.pack(side="right", fill="y")
        self.controls_canvas.pack(side="left", fill="both", expand=True)

        self.controls_panel = ttk.Frame(self.controls_canvas, style="Panel.TFrame", padding=12)
        self.controls_canvas_window = self.controls_canvas.create_window((0, 0), window=self.controls_panel, anchor="nw")
        self.controls_panel.bind("<Configure>", self._on_controls_panel_configure)
        self.controls_canvas.bind("<Configure>", self._on_controls_canvas_configure)
        self.controls_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_table_view(self.table_panel)
        self._build_controls(self.controls_panel)

    def _build_table_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=4)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=2, minsize=190)

        info = ttk.Frame(parent, style="Panel.TFrame")
        info.grid(row=0, column=0, sticky="ew")

        self.hand_info = ttk.Label(info, text="Hand #0", style="Meta.TLabel")
        self.hand_info.grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.stack_info = ttk.Label(info, text="Stack: $1000", style="Meta.TLabel")
        self.stack_info.grid(row=0, column=1, sticky="w", padx=(0, 16))
        self.pot_info = ttk.Label(info, text="Pot: $0", style="Meta.TLabel")
        self.pot_info.grid(row=0, column=2, sticky="w", padx=(0, 16))
        self.street_info = ttk.Label(info, text="Street: Pre-game", style="Meta.TLabel")
        self.street_info.grid(row=0, column=3, sticky="w", padx=(0, 16))
        self.call_info = ttk.Label(info, text="To Call: $0", style="Meta.TLabel")
        self.call_info.grid(row=0, column=4, sticky="w")

        board = ttk.Frame(parent, style="Panel.TFrame")
        board.grid(row=1, column=0, sticky="nsew", pady=(12, 10))

        opp_label = ttk.Label(board, text="Opponent", style="Meta.TLabel")
        opp_label.pack(anchor="w", pady=(0, 4))
        self.opponent_cards_frame = ttk.Frame(board, style="Panel.TFrame")
        self.opponent_cards_frame.pack(anchor="w", pady=(0, 12))

        comm_label = ttk.Label(board, text="Community", style="Meta.TLabel")
        comm_label.pack(anchor="w", pady=(0, 4))
        self.community_cards_frame = ttk.Frame(board, style="Panel.TFrame")
        self.community_cards_frame.pack(anchor="w", pady=(0, 12))

        player_label = ttk.Label(board, text="You", style="Meta.TLabel")
        player_label.pack(anchor="w", pady=(0, 4))
        self.player_cards_frame = ttk.Frame(board, style="Panel.TFrame")
        self.player_cards_frame.pack(anchor="w", pady=(0, 8))

        ai_box = ttk.Frame(parent, style="Panel.TFrame")
        ai_box.grid(row=2, column=0, sticky="ew")
        ttk.Label(ai_box, text="AI Recommendation", style="Meta.TLabel").pack(anchor="w")
        ai_text_frame = ttk.Frame(ai_box, style="Panel.TFrame")
        ai_text_frame.pack(fill="x", pady=(4, 0))
        self.ai_text = tk.Text(
            ai_text_frame,
            height=5,
            wrap="word",
            background="#113226",
            foreground="#eaf7ed",
            insertbackground="#eaf7ed",
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.ai_text_scroll = ttk.Scrollbar(ai_text_frame, orient="vertical", command=self.ai_text.yview)
        self.ai_text.configure(yscrollcommand=self.ai_text_scroll.set)
        self.ai_text.pack(side="left", fill="x", expand=True)
        self.ai_text_scroll.pack(side="right", fill="y")
        self.ai_text.configure(state="disabled")

        log_box = ttk.Frame(parent, style="Panel.TFrame")
        log_box.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        log_box.rowconfigure(1, weight=1)
        log_box.columnconfigure(0, weight=1)
        ttk.Label(log_box, text="Hand Log", style="Meta.TLabel").pack(anchor="w")
        log_text_frame = ttk.Frame(log_box, style="Panel.TFrame")
        log_text_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.log_text = tk.Text(
            log_text_frame,
            height=10,
            wrap="word",
            background="#0d281d",
            foreground="#cfebd6",
            insertbackground="#cfebd6",
            relief="flat",
            font=("Consolas", 10),
        )
        self.log_text_scroll = ttk.Scrollbar(log_text_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_text_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text_scroll.pack(side="right", fill="y")
        self.log_text.configure(state="disabled")

    def _on_controls_panel_configure(self, _event=None) -> None:
        self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all"))

    def _positions_for_players(self, num_players: int) -> list[str]:
        clamped = max(2, min(10, int(num_players)))
        return POSITIONS_BY_COUNT.get(clamped, POSITIONS_BY_COUNT[2])

    def _preflop_order(self, positions: list[str]) -> list[str]:
        if len(positions) <= 2:
            return list(positions)
        if "UTG" in positions:
            utg_index = positions.index("UTG")
            return positions[utg_index:] + positions[:utg_index]
        return list(positions)

    def _update_position_details(self) -> None:
        try:
            num_players = max(2, min(10, int(self.players_var.get())))
        except Exception:
            num_players = 2

        positions = self._positions_for_players(num_players)
        selected = self.position_var.get() if self.position_var.get() in positions else positions[0]
        order = self._preflop_order(positions)
        before = order.index(selected) if selected in order else 0
        after = len(order) - before - 1
        self.position_details_label.configure(
            text=f"Pre-flop before you: {before} | after you: {after}"
        )

    def _refresh_opponent_selector(self) -> None:
        try:
            num_players = max(2, min(10, int(self.players_var.get())))
        except Exception:
            num_players = 2

        labels = [f"Opponent {idx}" for idx in range(1, num_players)]
        if not labels:
            labels = ["Opponent 1"]
        self.opponent_labels = labels
        self.opp_player_combo.configure(values=labels)
        if self.opp_player_var.get() not in labels:
            self.opp_player_var.set(labels[0])

    def _on_players_or_position_changed(self) -> None:
        if self._updating_position_ui:
            return

        self._updating_position_ui = True
        try:
            try:
                num_players = max(2, min(10, int(self.players_var.get())))
            except Exception:
                num_players = 2
                self.players_var.set(num_players)

            positions = self._positions_for_players(num_players)
            self.position_combo.configure(values=positions)
            if self.position_var.get() not in positions:
                default_pos = "BB" if "BB" in positions else positions[0]
                self.position_var.set(default_pos)

            self._update_position_details()
            self._refresh_opponent_selector()
        finally:
            self._updating_position_ui = False

    def _on_players_var_change(self, *_args) -> None:
        self._on_players_or_position_changed()

    def _on_position_var_change(self, *_args) -> None:
        self._update_position_details()

    def _init_opponent_states(self) -> None:
        """Initialize opponent state tracking for the hand."""
        self.opponent_states = {}
        for label in self.opponent_labels:
            self.opponent_states[label] = {"folded": False, "contributed": 0, "acted_this_street": False}
        self.current_opponent_index = 0
        self.player_has_acted_this_street = False

    def _reset_opponent_acted_flags(self) -> None:
        for opp_name in self.opponent_states:
            self.opponent_states[opp_name]["acted_this_street"] = False

    def _all_active_opponents_acted(self) -> bool:
        active = [name for name, state in self.opponent_states.items() if not state.get("folded", False)]
        if not active:
            return True
        return all(self.opponent_states[name].get("acted_this_street", False) for name in active)

    def _get_next_active_opponent(self) -> str | None:
        """Get the next opponent who has not acted this street and has not folded."""
        start_idx = self.current_opponent_index
        for i in range(len(self.opponent_labels)):
            idx = (start_idx + i) % len(self.opponent_labels)
            opp_name = self.opponent_labels[idx]
            opp_state = self.opponent_states.get(opp_name, {})
            if not opp_state.get("folded", False) and not opp_state.get("acted_this_street", False):
                self.current_opponent_index = idx
                return opp_name
        return None

    def _is_betting_round_complete(self) -> bool:
        """Check if all opponents have acted and amounts match or are all-in."""
        # Count unfolded opponents
        unfolded = [o for o in self.opponent_labels if not self.opponent_states[o].get("folded", False)]
        if len(unfolded) == 0:
            return True  # Everyone folded
        
        # Check if player acted this street
        if not self.player_has_acted_this_street:
            return False
        
        # All unfolded opponents should have matched the bet or be all-in
        max_bet = max(self.opponent_states[o].get("contributed", 0) for o in unfolded)
        for opp_name in unfolded:
            if self.opponent_states[opp_name].get("contributed", 0) != max_bet:
                return False
        return True

    def _on_controls_canvas_configure(self, event) -> None:
        self.controls_canvas.itemconfigure(self.controls_canvas_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if self.controls_canvas.winfo_exists():
            self.controls_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_root_configure(self, event) -> None:
        if event.widget is not self:
            return
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(80, self._apply_layout_scaling)

    def _apply_layout_scaling(self) -> None:
        total_width = max(1120, self.winfo_width())
        target_controls_width = int(total_width * 0.33)
        target_controls_width = max(360, min(470, target_controls_width))
        self.controls_canvas.configure(width=target_controls_width)

        total_height = max(720, self.winfo_height())
        if total_height < 780:
            self.ai_text.configure(height=4)
            self.log_text.configure(height=8)
        elif total_height > 900:
            self.ai_text.configure(height=6)
            self.log_text.configure(height=12)
        else:
            self.ai_text.configure(height=5)
            self.log_text.configure(height=10)

    def _build_controls(self, parent: ttk.Frame) -> None:
        setup = ttk.LabelFrame(parent, text="Game Setup", padding=12)
        setup.pack(fill="x", pady=(0, 12))

        ttk.Label(setup, text="Players:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.players_var = tk.IntVar(value=2)
        self.players_spin = ttk.Spinbox(setup, from_=2, to=10, textvariable=self.players_var, width=8, command=self._on_players_or_position_changed)
        self.players_spin.grid(row=0, column=1, sticky="ew", padx=(0, 2), pady=4)

        ttk.Label(setup, text="Position:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.position_var = tk.StringVar(value="BB")
        self.position_combo = ttk.Combobox(setup, values=[], textvariable=self.position_var, state="readonly", width=10)
        self.position_combo.grid(row=1, column=1, sticky="ew", padx=(0, 2), pady=4)
        self.position_details_label = ttk.Label(setup, text="", style="Meta.TLabel")
        self.position_details_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ttk.Label(setup, text="Hole Cards:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.hole_var = tk.StringVar(value="Ah Kd")
        self.hole_entry = ttk.Entry(setup, textvariable=self.hole_var)
        self.hole_entry.grid(row=3, column=1, sticky="ew", padx=(0, 2), pady=4)

        self.play_blind_var = tk.BooleanVar(value=False)
        self.play_blind_check = ttk.Checkbutton(
            setup,
            text="Play Blind (hide/ignore hole cards)",
            variable=self.play_blind_var,
            command=self._on_toggle_play_blind,
        )
        self.play_blind_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 6))

        ttk.Label(setup, text="Initial Pot:").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self.initial_pot_var = tk.IntVar(value=15)
        self.initial_pot_entry = ttk.Entry(setup, textvariable=self.initial_pot_var)
        self.initial_pot_entry.grid(row=5, column=1, sticky="ew", padx=(0, 2), pady=4)

        self.start_btn = ttk.Button(setup, text="Start Hand", style="Accent.TButton", command=self.start_hand)
        self.start_btn.grid(row=6, column=0, columnspan=2, sticky="ew", padx=(0, 2), pady=(10, 2), ipady=2)
        setup.columnconfigure(1, weight=1)

        street = ttk.LabelFrame(parent, text="Street Control", padding=12)
        street.pack(fill="x", pady=(0, 12))

        ttk.Label(street, text="Community Input:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.community_var = tk.StringVar(value="")
        self.community_entry = ttk.Entry(street, textvariable=self.community_var)
        self.community_entry.grid(row=0, column=1, sticky="ew", padx=(0, 2), pady=4)

        self.flop_btn = ttk.Button(street, text="Deal Flop", style="Action.TButton", command=lambda: self.deal_street("flop"))
        self.flop_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(8, 4), ipady=1)
        self.turn_btn = ttk.Button(street, text="Deal Turn", style="Action.TButton", command=lambda: self.deal_street("turn"))
        self.turn_btn.grid(row=1, column=1, sticky="ew", padx=(4, 2), pady=(8, 4), ipady=1)
        self.river_btn = ttk.Button(street, text="Deal River", style="Action.TButton", command=lambda: self.deal_street("river"))
        self.river_btn.grid(row=2, column=0, sticky="ew", padx=(0, 4), pady=4, ipady=1)
        self.showdown_btn = ttk.Button(street, text="Showdown", style="Action.TButton", command=self.showdown)
        self.showdown_btn.grid(row=2, column=1, sticky="ew", padx=(4, 2), pady=4, ipady=1)
        street.columnconfigure(0, weight=1)
        street.columnconfigure(1, weight=1)

        opp = ttk.LabelFrame(parent, text="Opponent Action", padding=12)
        opp.pack(fill="x", pady=(0, 12))

        ttk.Label(opp, text="Opponent:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.opp_player_var = tk.StringVar(value="Opponent 1")
        self.opp_player_combo = ttk.Combobox(opp, values=["Opponent 1"], textvariable=self.opp_player_var, state="readonly")
        self.opp_player_combo.grid(row=0, column=1, sticky="ew", padx=(0, 2), pady=4)

        ttk.Label(opp, text="Action:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.opp_action_var = tk.StringVar(value="Check")
        self.opp_combo = ttk.Combobox(opp, values=["Check", "Call", "Bet / Raise", "Fold"], textvariable=self.opp_action_var, state="readonly")
        self.opp_combo.grid(row=1, column=1, sticky="ew", padx=(0, 2), pady=4)

        ttk.Label(opp, text="Amount:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.opp_amount_var = tk.IntVar(value=0)
        self.opp_amount_entry = ttk.Entry(opp, textvariable=self.opp_amount_var)
        self.opp_amount_entry.grid(row=2, column=1, sticky="ew", padx=(0, 2), pady=4)

        self.process_opp_btn = ttk.Button(opp, text="Process Opponent", style="Action.TButton", command=self.process_opponent_action)
        self.process_opp_btn.grid(row=3, column=0, columnspan=2, sticky="ew", padx=(0, 2), pady=(10, 2), ipady=2)
        opp.columnconfigure(1, weight=1)

        player = ttk.LabelFrame(parent, text="Your Action", padding=12)
        player.pack(fill="x")

        self.ask_ai_btn = ttk.Button(player, text="Get AI Suggestion", style="Accent.TButton", command=self.get_ai_decision)
        self.ask_ai_btn.grid(row=0, column=0, columnspan=3, sticky="ew", padx=(0, 2), pady=(0, 10), ipady=2)

        ttk.Separator(player, orient="horizontal").grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 10))

        self.check_btn = ttk.Button(player, text="Check", style="Action.TButton", command=lambda: self.apply_player_action("CHECK"))
        self.check_btn.grid(row=2, column=0, sticky="ew", padx=(0, 4), pady=4, ipady=1)
        self.call_btn = ttk.Button(player, text="Call", style="Action.TButton", command=lambda: self.apply_player_action("CALL"))
        self.call_btn.grid(row=2, column=1, sticky="ew", padx=4, pady=4, ipady=1)
        self.fold_btn = ttk.Button(player, text="Fold", style="Action.TButton", command=lambda: self.apply_player_action("FOLD"))
        self.fold_btn.grid(row=2, column=2, sticky="ew", padx=(4, 2), pady=4, ipady=1)

        ttk.Label(player, text="Raise To:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(10, 4))
        self.raise_var = tk.IntVar(value=0)
        self.raise_entry = ttk.Entry(player, textvariable=self.raise_var)
        self.raise_entry.grid(row=3, column=1, sticky="ew", padx=4, pady=(10, 4))

        self.raise_btn = ttk.Button(player, text="Raise", style="Action.TButton", command=lambda: self.apply_player_action("RAISE"))
        self.raise_btn.grid(row=3, column=2, sticky="ew", padx=(4, 2), pady=(10, 4), ipady=1)

        ttk.Separator(player, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 8))

        self.allin_btn = ttk.Button(player, text="All-In", style="Action.TButton", command=lambda: self.apply_player_action("ALL-IN"))
        self.allin_btn.grid(row=5, column=0, columnspan=3, sticky="ew", padx=(0, 2), pady=(2, 2), ipady=2)

        for c in range(3):
            player.columnconfigure(c, weight=1)

        self.players_var.trace_add("write", self._on_players_var_change)
        self.position_var.trace_add("write", self._on_position_var_change)
        self._on_players_or_position_changed()

    def _load_agent(self) -> None:
        api_key = load_api_key()
        self.agent = GeminiPokerAgent(api_key=api_key)

        if api_key and self.agent.client is not None:
            self._set_status("Gemini connected")
            self._log("Gemini agent initialized.")
        elif not api_key:
            self._set_status("Gemini unavailable (.env missing key)")
            self._log("No GEMINI_API_KEY found in .env. Running fallback strategy.")
        else:
            self._set_status("Gemini unavailable (fallback mode)")
            self._log("GEMINI_API_KEY found but Gemini client failed (invalid key, SDK, or network). Running fallback strategy.")

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_ai_text(self, text: str) -> None:
        self.ai_text.configure(state="normal")
        self.ai_text.delete("1.0", "end")
        self.ai_text.insert("1.0", text)
        self.ai_text.configure(state="disabled")

    def _card_file_for_code(self, card_code: str) -> str:
        c = (card_code or "").strip().upper()
        if len(c) < 2:
            raise ValueError(f"Invalid card: {card_code}")

        suit_key = c[-1].lower()
        rank_key = c[:-1]
        if suit_key not in SUIT_MAP or rank_key not in RANK_MAP:
            raise ValueError(f"Invalid card code: {card_code}")

        suit = SUIT_MAP[suit_key]
        rank = RANK_MAP[rank_key]
        return f"{suit}_{rank}.png"

    def _download_card_asset(self, filename: str) -> str:
        local_path = os.path.join(self.assets_dir, filename)
        if os.path.exists(local_path):
            return local_path

        url = f"{CARD_BASE_URL}/{filename}"
        request.urlretrieve(url, local_path)
        return local_path

    def _get_card_photo(self, card_code: str) -> tk.PhotoImage:
        if card_code in self.card_image_cache:
            return self.card_image_cache[card_code]

        filename = self._card_file_for_code(card_code)
        card_path = self._download_card_asset(filename)
        image = tk.PhotoImage(file=card_path)

        if image.width() > 170:
            image = image.subsample(2, 2)

        self.card_image_cache[card_code] = image
        return image

    def _get_back_photo(self) -> tk.PhotoImage:
        key = "_back_"
        if key in self.card_image_cache:
            return self.card_image_cache[key]

        path = self._download_card_asset("back_dark.png")
        image = tk.PhotoImage(file=path)
        if image.width() > 170:
            image = image.subsample(2, 2)
        self.card_image_cache[key] = image
        return image

    def _render_card_row(self, parent: ttk.Frame, cards: list[str], hidden: bool = False, slots: int | None = None) -> None:
        for child in parent.winfo_children():
            child.destroy()

        visible_cards = list(cards)
        if slots is not None:
            visible_cards = visible_cards[:slots]

        if slots is None:
            slots = max(1, len(visible_cards))

        for i in range(slots):
            frame = ttk.Frame(parent, style="Panel.TFrame")
            frame.pack(side="left", padx=5)
            code = visible_cards[i] if i < len(visible_cards) else ""

            if hidden and code:
                photo = self._get_back_photo()
                label = ttk.Label(frame, image=photo)
                label.image = photo
                label.pack()
                continue

            if not code:
                ttk.Label(frame, text="--", style="CardSlot.TLabel", width=8).pack(ipadx=20, ipady=35)
                continue

            try:
                photo = self._get_card_photo(code)
                label = ttk.Label(frame, image=photo)
                label.image = photo
                label.pack()
            except Exception:
                ttk.Label(frame, text=code, style="CardSlot.TLabel", width=8).pack(ipadx=20, ipady=35)

    def _update_board(self) -> None:
        self._render_card_row(self.opponent_cards_frame, ["XX", "XX"], hidden=True, slots=2)
        self._render_card_row(self.community_cards_frame, self.community_cards, hidden=False, slots=5)
        if self.play_blind:
            self._render_card_row(self.player_cards_frame, ["XX", "XX"], hidden=True, slots=2)
        else:
            self._render_card_row(self.player_cards_frame, self.hole_cards, hidden=False, slots=2)

    def _update_header(self) -> None:
        street_text = "Pre-game" if self.current_street < 0 else self.street_names[self.current_street]
        self.hand_info.configure(text=f"Hand #{self.hand_number}")
        self.stack_info.configure(text=f"Stack: ${self.my_stack}")
        self.pot_info.configure(text=f"Pot: ${self.pot_size}")
        self.street_info.configure(text=f"Street: {street_text}")
        self.call_info.configure(text=f"To Call: ${self.amount_to_call}")

    def _set_enabled(self, widget, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        if isinstance(widget, ttk.Combobox):
            widget.configure(state="readonly" if enabled else "disabled")
        else:
            widget.configure(state=state)

    def _update_ui_state(self) -> None:
        pre = self.phase == "pre_game"
        opponent_turn = self.phase == "opponent_action"
        player_turn = self.phase == "player_action"
        street_ready = self.phase == "street_ready"

        self._set_enabled(self.players_spin, pre)
        self._set_enabled(self.position_combo, pre)
        self._set_enabled(self.hole_entry, pre and not self.play_blind_var.get())
        self._set_enabled(self.play_blind_check, pre)
        self._set_enabled(self.initial_pot_entry, pre)
        self._set_enabled(self.start_btn, pre)

        # Auto-set next opponent and provide instruction
        if opponent_turn:
            if self._all_active_opponents_acted():
                if self.player_has_acted_this_street:
                    self.amount_to_call = 0
                    self.phase = "street_ready"
                    self._set_ai_text("All opponents have responded. Betting round complete.")
                    self._log("Betting round complete.")
                else:
                    self.phase = "player_action"
                    self._set_ai_text("All opponents have acted. Your turn.\nClick 'Get AI Suggestion' for recommendation.")
                self._update_ui_state()
                return
            next_opp = self._get_next_active_opponent()
            if next_opp:
                self.opp_player_var.set(next_opp)
                self._set_ai_text(f"Waiting for {next_opp}'s action.\nAmount to call: ${self.amount_to_call}")
            else:
                self.phase = "player_action"
                self._set_ai_text("All opponents have acted. Your turn!\nClick 'Get AI Suggestion' for recommendation.")
                self._update_ui_state()
                return

        self._set_enabled(self.opp_player_combo, opponent_turn)
        self._set_enabled(self.opp_combo, opponent_turn)
        self._set_enabled(self.opp_amount_entry, opponent_turn)
        self._set_enabled(self.process_opp_btn, opponent_turn)

        self._set_enabled(self.ask_ai_btn, player_turn)

        self._set_enabled(self.check_btn, player_turn and self.amount_to_call == 0)
        self._set_enabled(self.call_btn, player_turn and self.amount_to_call > 0)
        self._set_enabled(self.fold_btn, player_turn)
        self._set_enabled(self.raise_entry, player_turn)
        self._set_enabled(self.raise_btn, player_turn)
        self._set_enabled(self.allin_btn, player_turn)

        self._set_enabled(self.community_entry, street_ready and self.current_street < 3)
        self._set_enabled(self.flop_btn, street_ready and self.current_street == 0)
        self._set_enabled(self.turn_btn, street_ready and self.current_street == 1)
        self._set_enabled(self.river_btn, street_ready and self.current_street == 2)
        self._set_enabled(self.showdown_btn, street_ready and self.current_street == 3)

        self._update_header()
        self._update_board()

    def _parse_cards(self, text: str) -> list[str]:
        cards = [part.strip() for part in text.replace(",", " ").split() if part.strip()]
        for card in cards:
            self._card_file_for_code(card)
        return cards

    def _current_state_for_ai(self) -> dict:
        community_text = " ".join(self.community_cards) if self.community_cards else "None (Pre-flop)"
        hole_text = "Unknown (Playing Blind)" if self.play_blind else " ".join(self.hole_cards)
        history_text = " | ".join(self.opponent_history[-12:]) if self.opponent_history else self.last_opponent_action
        return {
            "hole_cards": hole_text,
            "community_cards": community_text,
            "my_stack": self.my_stack,
            "pot_size": self.pot_size,
            "amount_to_call": self.amount_to_call,
            "opponent_actions": history_text,
            "num_players": self.num_players,
            "my_position": self.my_position,
        }

    def start_hand(self) -> None:
        try:
            self.play_blind = bool(self.play_blind_var.get())
            cards = []
            if not self.play_blind:
                cards = self._parse_cards(self.hole_var.get())
                if len(cards) != 2:
                    raise ValueError("Enter exactly two hole cards, e.g. Ah Kd")

            self.hand_number += 1
            self.my_stack = 1000
            self.pot_size = int(self.initial_pot_var.get())
            if self.pot_size < 0:
                raise ValueError("Initial pot cannot be negative")

            self.hole_cards = cards
            self.community_cards = []
            self.amount_to_call = 0
            self.current_street = 0
            self.num_players = int(self.players_var.get())
            self.my_position = self.position_var.get().strip().upper() or "BB"
            self.last_opponent_action = "No actions yet."
            self.opponent_history = []
            self.phase = "opponent_action"

            self.community_var.set("")
            self.raise_var.set(0)
            self.opp_amount_var.set(0)
            self._refresh_opponent_selector()
            self._init_opponent_states()
            self._set_ai_text("Waiting for opponent action.")
            mode_text = "blind mode" if self.play_blind else "normal mode"
            self._log(f"Started hand #{self.hand_number} ({mode_text}) as {self.my_position} with {self.num_players} players.")
            self._update_ui_state()
        except Exception as exc:
            messagebox.showerror("Start Hand", str(exc))

    def _on_toggle_play_blind(self) -> None:
        self.play_blind = bool(self.play_blind_var.get())
        self._update_ui_state()

    def process_opponent_action(self) -> None:
        if self.phase != "opponent_action":
            return

        opponent_name = self.opp_player_var.get().strip() or "Opponent"
        action = self.opp_action_var.get()
        try:
            amount = int(self.opp_amount_var.get())
        except Exception:
            amount = 0

        if amount < 0:
            messagebox.showerror("Opponent Action", "Amount cannot be negative")
            return

        opp_state = self.opponent_states.get(opponent_name, {"folded": False, "contributed": 0})

        if action == "Fold":
            opp_state["folded"] = True
            opp_state["acted_this_street"] = True
            self.opponent_states[opponent_name] = opp_state
            unfolded_count = sum(1 for o in self.opponent_states.values() if not o.get("folded", False))
            if unfolded_count == 0:
                self.my_stack += self.pot_size
                self._log(f"{opponent_name} folded. You win ${self.pot_size}.")
                self._end_hand("All opponents folded. Start a new hand.")
                return
            self.last_opponent_action = f"{opponent_name} folded."
            self.opponent_history.append(self.last_opponent_action)
            self._log(self.last_opponent_action)
            # Move to next opponent
            self.current_opponent_index = (self.current_opponent_index + 1) % len(self.opponent_labels)
            self.phase = "opponent_action"
            self._update_ui_state()
            return

        if action == "Check":
            if self.amount_to_call > 0:
                messagebox.showerror("Opponent Action", "Cannot check when there is an amount to call")
                return
            opp_state["acted_this_street"] = True
            self.opponent_states[opponent_name] = opp_state
            self.last_opponent_action = f"{opponent_name} checked."
            self.opponent_history.append(self.last_opponent_action)
            self._log(self.last_opponent_action)
            # Move to next opponent
            self.current_opponent_index = (self.current_opponent_index + 1) % len(self.opponent_labels)
            self.phase = "opponent_action"
            self._update_ui_state()
            return

        if action == "Call":
            if amount < self.amount_to_call:
                messagebox.showerror("Opponent Action", f"Call amount must be at least ${self.amount_to_call}")
                return
            self.pot_size += amount
            opp_state["contributed"] = self.opponent_states[opponent_name].get("contributed", 0) + amount
            opp_state["acted_this_street"] = True
            self.opponent_states[opponent_name] = opp_state
            self.last_opponent_action = f"{opponent_name} called ${amount}."
            self.opponent_history.append(self.last_opponent_action)
            self._log(f"{self.last_opponent_action} Pot is now ${self.pot_size}.")
            # Move to next opponent or player
            self.current_opponent_index = (self.current_opponent_index + 1) % len(self.opponent_labels)
            self.phase = "opponent_action"
            self._update_ui_state()
            return

        if action == "Bet / Raise":
            if amount <= self.amount_to_call:
                messagebox.showerror("Opponent Action", f"Raise must be greater than ${self.amount_to_call}")
                return
            self.pot_size += amount
            opp_state["contributed"] = self.opponent_states[opponent_name].get("contributed", 0) + amount
            opp_state["acted_this_street"] = True
            self.opponent_states[opponent_name] = opp_state
            self.amount_to_call = amount
            self.last_opponent_action = f"{opponent_name} raised to ${amount}."
            self.opponent_history.append(self.last_opponent_action)
            self._log(f"{self.last_opponent_action} Pot is now ${self.pot_size}.")
            self.player_has_acted_this_street = False  # Reset player action since new bet
            # Move to next opponent to respond to raise
            self.current_opponent_index = (self.current_opponent_index + 1) % len(self.opponent_labels)
            self.phase = "opponent_action"
            self._update_ui_state()
            return

    def get_ai_decision(self) -> None:
        if self.phase != "player_action":
            return

        decision = self.agent.get_action(self._current_state_for_ai())
        action = decision.get("action", "CHECK")
        raise_amount = decision.get("raise_amount", 0)
        reasoning = decision.get("reasoning", "No reasoning.")

        self._set_ai_text(f"Action: {action}\nRaise To: ${raise_amount}\nReason: {reasoning}")
        self._log(f"AI suggests: {action} (raise to ${raise_amount}).")
        self._update_ui_state()

    def apply_player_action(self, action: str) -> None:
        if self.phase != "player_action":
            return

        self.player_has_acted_this_street = True

        if action == "FOLD":
            self._log(f"You folded. Opponents win ${self.pot_size}.")
            self._end_hand("You folded. Start a new hand.")
            return

        if action == "CHECK":
            if self.amount_to_call > 0:
                messagebox.showerror("Player Action", "Cannot check when there is an amount to call")
                return
            self._log("You checked.")
            self.phase = "street_ready"
            self._log("Betting round complete.")
            self._update_ui_state()
            return

        if action == "CALL":
            if self.amount_to_call <= 0:
                self._log("Nothing to call. Treated as check.")
                self.phase = "street_ready"
                self._log("Betting round complete.")
                self._update_ui_state()
                return
            if self.my_stack < self.amount_to_call:
                messagebox.showerror("Player Action", "Not enough chips to call")
                return
            self.my_stack -= self.amount_to_call
            self.pot_size += self.amount_to_call
            self._log(f"You called ${self.amount_to_call}. Pot is now ${self.pot_size}.")
            self.amount_to_call = 0
            self.phase = "street_ready"
            self._log("Betting round complete.")
            self._update_ui_state()
            return

        if action == "RAISE":
            try:
                raise_to = int(self.raise_var.get())
            except Exception:
                raise_to = 0

            if raise_to <= self.amount_to_call:
                messagebox.showerror("Player Action", f"Raise must be greater than ${self.amount_to_call}")
                return
            if raise_to > self.my_stack:
                messagebox.showerror("Player Action", "Not enough chips for that raise")
                return

            self.my_stack -= raise_to
            self.pot_size += raise_to
            self.amount_to_call = raise_to
            self._log(f"You raised to ${raise_to}. Pot is now ${self.pot_size}.")
            self.player_has_acted_this_street = True
            self._reset_opponent_acted_flags()
            self.phase = "opponent_action"
            self.current_opponent_index = 0
            self._update_ui_state()
            return

        if action == "ALL-IN":
            if self.my_stack <= 0:
                messagebox.showerror("Player Action", "No chips left to go all-in")
                return
            allin = self.my_stack
            self.my_stack = 0
            self.pot_size += allin
            self.amount_to_call = allin
            self._log(f"You went all-in for ${allin}. Pot is now ${self.pot_size}.")
            self.player_has_acted_this_street = True
            self._reset_opponent_acted_flags()
            self.phase = "opponent_action"
            self.current_opponent_index = 0
            self._update_ui_state()
            return

    def deal_street(self, street: str) -> None:
        if self.phase != "street_ready":
            return

        text = self.community_var.get().strip()
        try:
            cards = self._parse_cards(text)
        except Exception as exc:
            messagebox.showerror("Deal Street", str(exc))
            return

        expected = 3 if street == "flop" else 1
        if len(cards) != expected:
            messagebox.showerror("Deal Street", f"{street.title()} needs {expected} card(s)")
            return

        if street == "flop" and self.current_street != 0:
            return
        if street == "turn" and self.current_street != 1:
            return
        if street == "river" and self.current_street != 2:
            return

        self.community_cards.extend(cards)
        self.community_var.set("")
        self.amount_to_call = 0
        self.player_has_acted_this_street = False
        self.last_opponent_action = "No actions yet on this street."
        self.opponent_history.append(f"Street moved to {street.title()}.")
        # Reset opponent contributions for new street
        for opp_name in self.opponent_states:
            self.opponent_states[opp_name]["contributed"] = 0
        self._reset_opponent_acted_flags()
        self.current_street += 1
        self.current_opponent_index = 0
        self.phase = "opponent_action"
        self._log(f"Dealt {street}. Community: {' '.join(self.community_cards)}")
        self._update_ui_state()

    def showdown(self) -> None:
        if self.phase != "street_ready" or self.current_street != 3:
            return

        self._log("Showdown reached. Resolve winner manually and start next hand.")
        self._end_hand("Showdown complete. Start a new hand.")

    def _end_hand(self, message: str) -> None:
        self.phase = "pre_game"
        self.current_street = -1
        self.amount_to_call = 0
        self.community_cards = []
        self.hole_cards = []
        self.opponent_history = []
        self.opponent_states = {}
        self.current_opponent_index = 0
        self.player_has_acted_this_street = False
        self.play_blind = bool(self.play_blind_var.get())
        self.community_var.set("")
        self.raise_var.set(0)
        self.opp_amount_var.set(0)
        self._on_players_or_position_changed()
        self._set_ai_text(message)
        self._update_ui_state()


def main() -> None:
    app = PokerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
