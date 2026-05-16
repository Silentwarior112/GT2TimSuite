import sys
import subprocess
import os
import struct
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# --- Pillow Library checker / installer ---
def bootstrap_dependencies():
    try:
        from PIL import Image, ImageTk, ImageDraw
        return True 
    except ImportError:
        root = tk.Tk()
        root.withdraw()
        user_choice = messagebox.askyesno(
            "Dependency Missing", 
            "GT2TimSuite relies on the 'Pillow' library.\n\n"
            "Do you want to install it now?"
        )
        if user_choice:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
                messagebox.showinfo("Success", "Pillow installed successfully.")
                root.destroy()
                # Tool will start
            except Exception as e:
                messagebox.showerror("Installation Failed", f"Could not install Pillow: {e}")
                root.destroy()
                sys.exit() # Closes itself
        else:
            root.destroy()
            sys.exit() # Closes itself

if bootstrap_dependencies():
    from PIL import Image, ImageTk, ImageDraw

class PDTimTool:
    def __init__(self, root):
        self.root = root
        self.root.title("GT2TimSuite by Silentwarior112")

        self.raw_data = None
        self.pixel_indices = []
        self.true_color_data = None
        self.width = self.height = 0
        self.boxes = [] 
        self.all_palettes = [] 
        self.tim_type = None 
        
        self.zoom = 4.0
        self.global_default_idx = 0
        self.active_box_idx = None
        self.resize_mode = None
        self.rect = None
        
        self.setup_ui()
        self.create_context_menu()

    def setup_ui(self):
        self.clut_var = tk.IntVar(value=0)
        self.main_container = tk.Frame(self.root, bg="#202020")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(self.main_container, bg="#333333", pady=5)
        top_bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(top_bar, text=" Load:", bg="#333333", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        tk.Button(top_bar, text="Tim / GT2 Sheet / Multi-Tim", command=self.load_file, width=24).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Load CLUT config", command=self.load_clut_config, width=15).pack(side=tk.LEFT, padx=5)
        tk.Frame(top_bar, width=2, bg="#555555", height=20).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Label(top_bar, text=" Converters:", bg="#333333", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        tk.Button(top_bar, text="Export to PNG(s)", command=self.export_png_dialog, width=14).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Bulk Tim to PNG", command=self.bulk_tim_to_png, width=14).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="PNG to Standard Tim", command=self.convert_png_to_tim, width=18).pack(side=tk.LEFT, padx=5)
        tk.Frame(top_bar, width=2, bg="#555555", height=20).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Label(top_bar, text=" Build:", bg="#333333", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=2)
        tk.Button(top_bar, text="Build 4bpp GT2 Tim Sheet", command=self.build_gt2_tim_sheet, width=22).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Build Standard Tim Sheet", command=self.build_standard_tim_sheet,width=22).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Pack Multi-File", command=self.build_multi_tim_container, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Pack TRP / BSP", command=self.build_trp_container, width=12).pack(side=tk.LEFT, padx=5)

        self.content_area = tk.Frame(self.main_container, bg="#202020")
        self.content_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(self.content_area, width=220, bg="#252526")
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        tk.Label(self.sidebar, text="Palette Window", fg="white", bg="#252526", font=("Arial", 9, "bold")).pack(pady=(10, 2))
        self.clut_ctrl_frame = tk.Frame(self.sidebar, bg="#252526")
        self.clut_ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(self.clut_ctrl_frame, text="CLUT search: \n Change this until you get \n the correct amount of palettes. \n Or, use arrow keys up/down to cycle \n palettes while hovering over a box.", fg="#aaa", bg="#252526", font=("Arial", 8)).pack(anchor="w")
        self.inc_spin = tk.Spinbox(self.clut_ctrl_frame, from_=1, to=999, width=4, command=self.load_palettes)
        self.inc_spin.delete(0, "end"); self.inc_spin.insert(0, "1")
        self.inc_spin.pack(anchor="w", pady=2)
        
        # --- Add these lines to unbind the arrow keys ---
        self.inc_spin.bind("<Up>", lambda e: "break")
        self.inc_spin.bind("<Down>", lambda e: "break")
        
        self.list_container = tk.Frame(self.sidebar, bg="#1e1e1e")
        self.list_container.pack(fill=tk.BOTH, expand=True, pady=5)
        self.clut_canvas = tk.Canvas(self.list_container, bg="#1e1e1e", highlightthickness=0)
        self.clut_scroll = tk.Scrollbar(self.list_container, orient="vertical", command=self.clut_canvas.yview)
        self.scrollable_frame = tk.Frame(self.clut_canvas, bg="#1e1e1e")
        self.scrollable_frame.bind("<Configure>", lambda e: self.clut_canvas.configure(scrollregion=self.clut_canvas.bbox("all")))
        self.clut_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.clut_canvas.configure(yscrollcommand=self.clut_scroll.set)
        self.clut_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.clut_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.view_window = tk.Frame(self.content_area, bg="#1a1a1a")
        self.view_window.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.view_window, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.clut_canvas.bind_all("<MouseWheel>", self._on_mousewheel_sidebar)
        self.sidebar.bind("<Enter>", self._bind_sidebar_mousewheel)
        self.sidebar.bind("<Leave>", self._unbind_sidebar_mousewheel)
        
        self.clut_canvas.bind("<Enter>", self._bind_sidebar_mousewheel)
        self.clut_canvas.bind("<Leave>", self._unbind_sidebar_mousewheel)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.check_hover)
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<MouseWheel>", self.handle_mousewheel)
        self.root.bind("<Up>", self.cycle_palette_down)
        self.root.bind("<Down>", self.cycle_palette_up)
        
    def _bind_sidebar_mousewheel(self, event):
        """Activates mousewheel listener when cursor enters sidebar"""
        self.root.bind_all("<MouseWheel>", self._on_mousewheel_sidebar)

    def _unbind_sidebar_mousewheel(self, event):
        """Deactivates mousewheel listener when cursor leaves sidebar"""
        self.root.unbind_all("<MouseWheel>")

    def _on_mousewheel_sidebar(self, event):
        """Scrolls the palette sidebar"""
        # Windows uses delta, usually 120 units per notch
        self.clut_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
    def create_progress_dialog(self, title, max_val):
        """Creates a centered progress popup"""
        from tkinter import ttk
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        
        # Center the dialog
        w, h = 350, 120
        root_x, root_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        root_w, root_h = self.root.winfo_width(), self.root.winfo_height()
        dialog.geometry(f"{w}x{h}+{root_x + (root_w//2 - w//2)}+{root_y + (root_h//2 - h//2)}")
        
        dialog.transient(self.root)
        dialog.grab_set()

        lbl = tk.Label(dialog, text="Starting...", font=("Arial", 9))
        lbl.pack(pady=10)
        
        pb = ttk.Progressbar(dialog, length=300, mode='determinate', maximum=max_val)
        pb.pack(pady=5)
        
        return dialog, pb, lbl
        
    def _on_mousewheel_sidebar(self, event):
        """Scrolls the palette sidebar only if the mouse is over it"""
        # Check if the widget under the mouse is a child of the sidebar
        widget = event.widget
        if str(widget).startswith(str(self.sidebar)):
            self.clut_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def decode_a1b5g5r5(self, v):
        r, g, b, stp = (v & 0x1F) << 3, ((v >> 5) & 0x1F) << 3, ((v >> 10) & 0x1F) << 3, (v >> 15) & 0x01
        if r == g == b == 0 and stp == 0: return (0, 0, 0, 0) # If all bits are 0, that would indicate a fully opaque black pixel because transparency flag is off, however the correct interpretation is fully transparent.
        if stp == 0: return (r, g, b, 255)
        max_c = max(r, g, b)
        # If black-key transparency mode is ON
        if stp == 1:
            if max_c == 0:
                return (0, 0, 0, 255) # Fully black and also transparent is impossible with black-keying, so make it opaque. This is probably never encountered
            target = 255
            alpha = max(1, (max_c * 255) // target) 
            return (min(255, (r * 255) // alpha), min(255, (g * 255) // alpha), min(255, (b * 255) // alpha), alpha)
        # If the color is opaque
        else:
            target = 214
            alpha = 255 if max_c >= target else max(1, (max_c * 255) // target)
            return (min(255, (r * 255) // alpha), min(255, (g * 255) // alpha), min(255, (b * 255) // alpha), alpha)

    def load_file(self):
        path = filedialog.askopenfilename()
        if not path: return
        with open(path, "rb") as f:
            data = f.read()
        self.pixel_indices, self.all_palettes, self.boxes, self.true_color_data = [], [], [], None
        
        magic = data[0:8]
        trp_1stTIM = data[4:12]
        trp_filecount = data[0:4]
        if magic == b"\x10\x00\x00\x00\x00\x00\x00\x00": self.parse_pd_16(data); return
        elif magic == b"\x10\x00\x00\x00\x08\x00\x00\x00": self.parse_std_16(data); return
        elif magic == b"\x10\x00\x00\x00\x09\x00\x00\x00": self.parse_std_256(data); return
        elif magic == b"\x10\x00\x00\x00\x02\x00\x00\x00": self.parse_std_true(data); return

        if len(data) >= 8:
            num_files = struct.unpack("<I", data[0:4])[0]
            if trp_1stTIM == b"\x10\x00\x00\x00\x02\x00\x00\x00" or trp_1stTIM == b"\x10\x00\x00\x00\x08\x00\x00\x00" or trp_1stTIM == b"\x10\x00\x00\x00\x09\x00\x00\x00":
                    if messagebox.askokcancel("Multi-TIM Detected", 
                                              "A multi-tim TRP / BSP package was detected. Select an output folder in the next step."):
                        self.parse_trp(data, num_files)
                    return
            elif 0 < num_files < 2048 and len(data) > (num_files * 4) + 4:
                first_off = struct.unpack("<I", data[4:8])[0]
                if first_off < len(data) and data[first_off:first_off+4] == b"\x10\x00\x00\x00":
                    if messagebox.askokcancel("Multi-TIM Detected", 
                                              "A multi-tim package was detected. Select an output folder in the next step."):
                        self.parse_multi_tim(data, num_files)
                    return
                elif first_off < len(data):
                    if messagebox.askokcancel("Multi-File Detected", 
                                              "A multi-file package was detected. Select an output folder in the next step."):
                        self.parse_multi_file(data, num_files)
                    return
        messagebox.showerror("Error", "Unknown format.")

    def parse_pd_16(self, data):
        self.tim_type, self.raw_data = 0, data
        h = struct.unpack("<8sIHHHH", data[:20])
        self.width, self.height = h[4]*4, h[5]
        px_bytes = data[20 : 20 + (h[4]*2 * h[5])]
        self.pixel_indices = [idx for b in px_bytes for idx in (b & 0x0F, (b >> 4) & 0x0F)]
        self.load_palettes()

    def parse_std_16(self, data):
        self.tim_type, self.raw_data = 8, data
        c_size = struct.unpack("<I", data[8:12])[0]
        c_per, num_p = struct.unpack("<HH", data[16:20])
        for p in range(num_p):
            pal = []
            for c in range(c_per):
                v = struct.unpack("<H", data[20+p*c_per*2+c*2:22+p*c_per*2+c*2])[0]
                pal.append(self.decode_a1b5g5r5(v))
            self.all_palettes.append(pal)
        h_off = 8 + c_size
        h_w, h = struct.unpack("<HH", data[h_off+8:h_off+12])
        self.width, self.height = h_w * 4, h
        px = data[h_off+12 : h_off+12 + (self.width*self.height // 2)]
        self.pixel_indices = [idx for b in px for idx in (b & 0x0F, (b >> 4) & 0x0F)]
        self.load_palettes()

    def parse_std_256(self, data):
        self.tim_type, self.raw_data = 9, data
        c_size = struct.unpack("<I", data[8:12])[0]
        c_per, num_p = struct.unpack("<HH", data[16:20])
        for p in range(num_p):
            self.all_palettes.append([self.decode_a1b5g5r5(struct.unpack("<H", data[20+p*c_per*2+c*2:22+p*c_per*2+c*2])[0]) for c in range(c_per)])
        h_off = 8 + c_size
        h_w, h = struct.unpack("<HH", data[h_off+8:h_off+12])
        self.width, self.height = h_w * 2, h
        self.pixel_indices = list(data[h_off+12 : h_off+12 + self.width*self.height])
        self.load_palettes()

    def parse_std_true(self, data):
        self.tim_type, self.raw_data = 2, data
        _, _, _, h_w, h = struct.unpack("<IHHHH", data[8:20])
        self.width, self.height, self.true_color_data = h_w, h, []
        for i in range(0, h_w*h*2, 2):
            self.true_color_data.append(self.decode_a1b5g5r5(struct.unpack("<H", data[20+i:22+i])[0]))
        self.display_sheet()
        
    def _bulk_parse_std_16(self, data):
        """Internal 4bpp parser: Returns (width, height, pixel_indices, palettes)"""
        c_size = struct.unpack("<I", data[8:12])[0]
        c_per, num_p = struct.unpack("<HH", data[16:20])
        palettes = []
        for p in range(num_p):
            pal = [self.decode_a1b5g5r5(struct.unpack("<H", data[20+p*c_per*2+c*2:22+p*c_per*2+c*2])[0]) for c in range(c_per)]
            palettes.append(pal)
        
        h_off = 8 + c_size
        h_w, h = struct.unpack("<HH", data[h_off+8:h_off+12])
        w = h_w * 4
        px_data = data[h_off+12 : h_off+12 + (w * h // 2)]
        indices = []
        for b in px_data:
            indices.extend([b & 0x0F, (b >> 4) & 0x0F])
        return w, h, indices, palettes

    def _bulk_parse_std_256(self, data):
        """Internal 8bpp parser: Returns (width, height, pixel_indices, palettes)"""
        c_size = struct.unpack("<I", data[8:12])[0]
        c_per, num_p = struct.unpack("<HH", data[16:20])
        palettes = []
        for p in range(num_p):
            pal = [self.decode_a1b5g5r5(struct.unpack("<H", data[20+p*c_per*2+c*2:22+p*c_per*2+c*2])[0]) for c in range(c_per)]
            palettes.append(pal)
            
        h_off = 8 + c_size
        h_w, h = struct.unpack("<HH", data[h_off+8:h_off+12])
        w = h_w * 2
        indices = list(data[h_off+12 : h_off+12 + w * h])
        return w, h, indices, palettes

    def _bulk_parse_std_true(self, data):
        """Internal TrueColor parser: Returns (width, height, rgba_pixels)"""
        _, _, _, h_w, h = struct.unpack("<IHHHH", data[8:20])
        rgba_pixels = []
        for i in range(0, h_w * h * 2, 2):
            rgba_pixels.append(self.decode_a1b5g5r5(struct.unpack("<H", data[20+i:22+i])[0]))
        return h_w, h, rgba_pixels

    def load_palettes(self):
        """Loads palettes and applies engine-side edge case handling for maxed RGB + STP"""
        for w in self.scrollable_frame.winfo_children(): w.destroy()
        if self.raw_data is None: return
        
        is_std = self.tim_type in [2, 8, 9]
        if is_std: 
            self.clut_ctrl_frame.pack_forget()
        else: 
            self.clut_ctrl_frame.pack(before=self.list_container, fill=tk.X, padx=5, pady=5)
        
        if not is_std:
            try: num_inc = int(self.inc_spin.get())
            except: num_inc = 1
            self.all_palettes = []
            
            # CLUT bytes are truncated to the next multiple of 4 CLUTs.
            start = len(self.raw_data) - (num_inc * 0x80)
            
            for i in range(num_inc * 4):
                off = start + (i * 0x20)
                if off + 32 > len(self.raw_data): break
                chunk = self.raw_data[off : off+32]
                
                # --- Step 1: Standard Decode ---
                raw_clut_values = [struct.unpack("<H", chunk[j:j+2])[0] for j in range(0, 32, 2)]
                decoded_pal = [self.decode_a1b5g5r5(v) for v in raw_clut_values]
                self.all_palettes.append(decoded_pal)
        
        # UI Refresh
        for i, pal in enumerate(self.all_palettes): 
            self.add_clut_to_ui(i, pal)
            
        self.scrollable_frame.update_idletasks()
        self.clut_canvas.config(scrollregion=self.clut_canvas.bbox("all"))
            
        self.global_default_idx = self.get_default_palette_idx()
        self.clut_var.set(self.global_default_idx)
        self.display_sheet()
        
    def load_clut_config(self):
        """Loads a config.json, restores boxes, and updates the palette window"""
        if self.raw_data is None:
            messagebox.showwarning("No Data", "Load a TIM file first.")
            return

        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            if "textures" not in data:
                messagebox.showerror("Error", "Invalid config file.")
                return

            self.boxes = []
            max_clut = 0
            
            for tex in data["textures"]:
                c_idx = int(tex.get("clut_global_idx", 0))
                if c_idx > max_clut:
                    max_clut = c_idx

                self.boxes.append({
                    "name": tex.get("name", self.get_unique_name()),
                    "x": int(tex.get("x", 0)),
                    "y": int(tex.get("y", 0)),
                    "w": int(tex.get("w", 16)),
                    "h": int(tex.get("h", 16)),
                    "clut_global_idx": c_idx,
                    "locked": tex.get("locked", False),
                    "black_bg": tex.get("black_bg", False)
                })
            
            # --- Sync Palette Window ---
            # Calculate required increment to show the highest used CLUT
            # Since 1 increment = 4 CLUTs, we divide by 4 and add 1
            needed_inc = (max_clut // 4) + 1
            
            # Update the Spinbox UI
            self.inc_spin.delete(0, "end")
            self.inc_spin.insert(0, str(needed_inc))
            
            # Trigger palette reload to rebuild the sidebar UI
            self.load_palettes() 

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")

    def add_clut_to_ui(self, idx, pal):
        row = tk.Frame(self.scrollable_frame, bg="#1e1e1e")
        row.pack(fill=tk.X, pady=1)
        row.bind("<Enter>", self._bind_sidebar_mousewheel)
        tk.Radiobutton(row, text=str(idx), value=idx, variable=self.clut_var, command=lambda: self.select_palette(idx), bg="#1e1e1e", fg="#ccc", selectcolor="#444", font=("Arial", 7)).pack(side=tk.LEFT)
        pc = tk.Canvas(row, width=144, height=10, highlightthickness=0)
        pc.pack(side=tk.LEFT, padx=2)
        for c in range(len(pal)):
            r, g, b, a = pal[c]
            pc.create_rectangle(c*(144/len(pal)), 0, (c+1)*(144/len(pal)), 10, fill=f'#{r:02x}{g:02x}{b:02x}' if a > 0 else "#1e1e1e", outline="")

    def select_palette(self, idx):
        self.global_default_idx = idx
        self.display_sheet()

    def get_default_palette_idx(self):
        for i, p in enumerate(self.all_palettes):
            if any(any(c[:3]) for c in p): return i
        return 0

    def display_sheet(self):
        is_tc = self.tim_type == 2
        if not is_tc and (not self.all_palettes or not self.pixel_indices): return
        base = self.create_checkerboard(self.width, self.height)
        if is_tc:
            full = Image.new("RGBA", (self.width, self.height))
            full.putdata(self.true_color_data)
            base.alpha_composite(full)
        else:
            bg_pal = self.all_palettes[self.global_default_idx]
            full = Image.new("RGBA", (self.width, self.height))
            full.putdata([bg_pal[i] for i in self.pixel_indices])
            mask = Image.new("L", (self.width, self.height), 255)
            mdraw = ImageDraw.Draw(mask)
            for b in self.boxes: mdraw.rectangle([b['x'], b['y'], b['x']+b['w']-1, b['y']+b['h']-1], fill=0)
            base.paste(full, (0, 0), mask)
            for b in self.boxes:
                pal = self.all_palettes[b['clut_global_idx'] if b['clut_global_idx'] < len(self.all_palettes) else 0]
                if b.get('black_bg'): ImageDraw.Draw(base).rectangle([b['x'], b['y'], b['x']+b['w']-1, b['y']+b['h']-1], fill="black")
                box_img = Image.new("RGBA", (b['w'], b['h']))
                pix = [pal[self.pixel_indices[py * self.width + px]] for py in range(b['y'], b['y']+b['h']) for px in range(b['x'], b['x']+b['w'])]
                box_img.putdata(pix)
                base.alpha_composite(box_img, (b['x'], b['y']))
        sw, sh = int(self.width * self.zoom), int(self.height * self.zoom)
        self.tk_img = ImageTk.PhotoImage(base.resize((sw, sh), Image.NEAREST))
        
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        # 3. Draw the Outside Border
        self.canvas.create_rectangle(-1, -1, sw, sh, outline="#606060", width=1)

        # 4. Draw Vector Overlays (Boxes and Labels)
        for b in self.boxes:
            z = self.zoom
            col = "orange" if b.get('locked') else "green"
            x1, y1 = b['x'] * z, b['y'] * z
            x2, y2 = (b['x'] + b['w']) * z, (b['y'] + b['h']) * z
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=col, width=2)
            
            lbl = f"{b['name']} (L)" if b.get('locked') else b['name']
            dim_txt = f"{b['w']}x{b['h']}"
            pal_txt = f"CLUT {b.get('clut_global_idx', 0)}" # NEW: Palette Index text
            
            self.canvas.create_text(x1 + 5, y1 + 5, text=lbl, fill="black", anchor="nw", font=("Arial", 10, "bold"))
            self.canvas.create_text(x1 + 4, y1 + 4, text=lbl, fill="yellow", anchor="nw", font=("Arial", 10, "bold"))
            self.canvas.create_text(x1 + 5, y1 + 25, text=dim_txt, fill="black", anchor="nw", font=("Arial", 9, "bold"))
            self.canvas.create_text(x1 + 4, y1 + 24, text=dim_txt, fill="cyan", anchor="nw", font=("Arial", 9, "bold"))
            self.canvas.create_text(x1 + 5, y1 + 41, text=pal_txt, fill="black", anchor="nw", font=("Arial", 9, "bold"))
            self.canvas.create_text(x1 + 4, y1 + 40, text=pal_txt, fill="#FF00FF", anchor="nw", font=("Arial", 9, "bold"))

        # Update scrollregion
        pad_w, pad_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.config(scrollregion=(-pad_w, -pad_h, sw + pad_w, sh + pad_h))

    def on_press(self, event):
        if not self.raw_data: return
        
        # Force focus to the canvas so key events register cleanly
        self.canvas.focus_set()
        
        self.px_start_x, self.px_start_y = self.get_snapped_pixel(event.x, event.y)
        self.drag_shdw_id = self.canvas.create_text(0, 0, text="", fill="black", font=("Arial", 12, "bold"))
        self.drag_label_id = self.canvas.create_text(0, 0, text="", fill="white", font=("Arial", 12, "bold"))
        
        self.rect = self.canvas.create_rectangle(0, 0, 0, 0, outline="cyan", dash=(4, 4))
        
        self.active_box_idx = None
        for i, b in enumerate(reversed(self.boxes)):
            if b['x'] <= self.px_start_x <= b['x']+b['w'] and b['y'] <= self.px_start_y <= b['y']+b['h']:
                self.active_box_idx = len(self.boxes) - 1 - i
                break
        
        if self.active_box_idx is not None:
            self.orig_box = self.boxes[self.active_box_idx].copy()
            self.drag_offset_x = self.px_start_x - self.orig_box['x']
            self.drag_offset_y = self.px_start_y - self.orig_box['y']

    def on_move(self, event):
        if not self.raw_data: return
        cx, cy = self.get_snapped_pixel(event.x, event.y)
        z = self.zoom
        
        if self.resize_mode:
            nb = self.orig_box.copy()
            if 'w' in self.resize_mode: 
                nb['x'] = max(0, min(cx, nb['x'] + nb['w'] - 1))
                nb['w'] = max(1, self.orig_box['w'] - (nb['x'] - self.orig_box['x']))
            if 'e' in self.resize_mode: 
                nb['w'] = max(1, min(cx, self.width) - nb['x'])
            if 'n' in self.resize_mode: 
                nb['y'] = max(0, min(cy, nb['y'] + nb['h'] - 1))
                nb['h'] = max(1, self.orig_box['h'] - (nb['y'] - self.orig_box['y']))
            if 's' in self.resize_mode: 
                nb['h'] = max(1, min(cy, self.height) - nb['y'])
            
            self.canvas.coords(self.rect, nb['x']*z, nb['y']*z, (nb['x']+nb['w'])*z, (nb['y']+nb['h'])*z)
            self.update_drag_feedback(event.x, event.y, nb['w'], nb['h'])
            
        elif self.active_box_idx is not None:
            nb = self.orig_box.copy()
            if not nb.get('locked'):
                new_x = cx - self.drag_offset_x
                new_y = cy - self.drag_offset_y
                nb['x'] = max(0, min(new_x, self.width - nb['w']))
                nb['y'] = max(0, min(new_y, self.height - nb['h']))
                self.canvas.coords(self.rect, nb['x']*z, nb['y']*z, (nb['x']+nb['w'])*z, (nb['y']+nb['h'])*z)
                self.update_drag_feedback(event.x, event.y, nb['w'], nb['h'])
                self.canvas.config(cursor="fleur")
            
        else:
            x0, x1 = sorted([self.px_start_x, cx])
            y0, y1 = sorted([self.px_start_y, cy])
            self.canvas.coords(self.rect, x0*z, y0*z, x1*z, y1*z)
            self.update_drag_feedback(event.x, event.y, x1-x0, y1-y0)

    def on_release(self, event):
        if not self.raw_data: return
        if hasattr(self, 'drag_label_id') and self.drag_label_id: self.canvas.delete(self.drag_label_id)
        if hasattr(self, 'drag_shdw_id') and self.drag_shdw_id: self.canvas.delete(self.drag_shdw_id)
        if self.rect: self.canvas.delete(self.rect)
        
        ex, ey = self.get_snapped_pixel(event.x, event.y)
        
        if self.resize_mode:
            b = self.boxes[self.active_box_idx]
            if 'w' in self.resize_mode:
                new_x = max(0, min(ex, b['x'] + b['w'] - 1))
                b['w'] = max(1, b['w'] - (new_x - b['x']))
                b['x'] = new_x
            if 'e' in self.resize_mode: 
                b['w'] = max(1, min(ex, self.width) - b['x'])
            if 'n' in self.resize_mode:
                new_y = max(0, min(ey, b['y'] + b['h'] - 1))
                b['h'] = max(1, b['h'] - (new_y - b['y']))
                b['y'] = new_y
            if 's' in self.resize_mode: 
                b['h'] = max(1, min(ey, self.height) - b['y'])
            self.resize_mode = None
            
        elif self.active_box_idx is not None:
            b = self.boxes[self.active_box_idx]
            if not b.get('locked'):
                new_x = ex - self.drag_offset_x
                new_y = ey - self.drag_offset_y
                b['x'] = max(0, min(new_x, self.width - b['w']))
                b['y'] = max(0, min(new_y, self.height - b['h']))
            
        else:
            x, y, w, h = min(self.px_start_x, ex), min(self.px_start_y, ey), abs(ex-self.px_start_x), abs(ey-self.px_start_y)
            if w > 1 and h > 1:
                self.boxes.append({"x": x, "y": y, "w": w, "h": h, 
                                   "clut_global_idx": self.global_default_idx, 
                                   "name": self.get_unique_name()})
        
        self.display_sheet()
        
    def update_drag_feedback(self, ex, ey, w, h):
        if hasattr(self, 'drag_label_id') and self.drag_label_id:
            txt = f"{w} x {h}"
            tx, ty = self.canvas.canvasx(ex) + 15, self.canvas.canvasy(ey) + 15
            self.canvas.coords(self.drag_shdw_id, tx + 2, ty + 2)
            self.canvas.itemconfig(self.drag_shdw_id, text=txt)
            self.canvas.coords(self.drag_label_id, tx, ty)
            self.canvas.itemconfig(self.drag_label_id, text=txt)

    def check_hover(self, event):
        if not self.raw_data: return
        px, py = self.get_snapped_pixel(event.x, event.y)
        self.resize_mode = self.active_box_idx = None
        self.canvas.config(cursor="cross")
        for i, b in enumerate(reversed(self.boxes)):
            m = 8 / self.zoom
            on_l, on_r = abs(px - b['x']) < m, abs(px - (b['x']+b['w'])) < m
            on_t, on_b = abs(py - b['y']) < m, abs(py - (b['y']+b['h'])) < m
            if b['x'] <= px <= b['x']+b['w'] and b['y'] <= py <= b['y']+b['h']:
                self.active_box_idx = len(self.boxes)-1-i
                if not b.get('locked'):
                    if on_l and on_t: self.resize_mode, cur = "nw", "size_nw_se"
                    elif on_r and on_t: self.resize_mode, cur = "ne", "size_ne_sw"
                    elif on_r and on_b: self.resize_mode, cur = "se", "size_nw_se"
                    elif on_l and on_b: self.resize_mode, cur = "sw", "size_ne_sw"
                    elif on_l or on_r: self.resize_mode, cur = ("w" if on_l else "e"), "sb_h_double_arrow"
                    elif on_t or on_b: self.resize_mode, cur = ("n" if on_t else "s"), "sb_v_double_arrow"
                    else: cur = "fleur"
                    self.canvas.config(cursor=cur)
                break

    def create_context_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Rename", command=self.menu_rename)
        self.menu.add_command(label="Set Palette to selected", command=self.menu_change_palette)
        self.menu.add_command(label="Toggle Lock", command=self.menu_toggle_lock)
        self.menu.add_command(label="Toggle Black Background", command=self.menu_toggle_black_bg)
        self.menu.add_command(label="Make Copy", command=self.menu_copy_box)
        self.menu.add_separator()
        self.menu.add_command(label="Delete", command=self.menu_delete, foreground="red")

    def show_context_menu(self, event):
        if self.active_box_idx is not None: self.menu.post(event.x_root, event.y_root)

    def menu_rename(self):
        b = self.boxes[self.active_box_idx]
        n = simpledialog.askstring(" ", "Set the name.", initialvalue=b['name'])
        if n: b['name'] = n; self.display_sheet()

    def menu_toggle_lock(self):
        self.boxes[self.active_box_idx]['locked'] = not self.boxes[self.active_box_idx].get('locked'); self.display_sheet()

    def menu_toggle_black_bg(self):
        self.boxes[self.active_box_idx]['black_bg'] = not self.boxes[self.active_box_idx].get('black_bg'); self.display_sheet()

    def menu_delete(self):
        self.boxes.pop(self.active_box_idx); self.display_sheet()
        
    def menu_change_palette(self):
        if self.active_box_idx is not None:
            self.boxes[self.active_box_idx]['clut_global_idx'] = self.global_default_idx
            self.display_sheet()
            
    def get_unique_name(self):
        """Finds the lowest available name in the format tex_[i]"""
        used_indices = set()
        for b in self.boxes:
            if b['name'].startswith("tex_"):
                try:
                    num = int(b['name'].split('_')[1])
                    used_indices.add(num)
                except (IndexError, ValueError):
                    continue

        i = 0
        while i in used_indices:
            i += 1
            
        return f"tex_{i}"
            
    def menu_copy_box(self):
        if self.active_box_idx is not None:
            source = self.boxes[self.active_box_idx]
            default_name = self.get_unique_name()
            new_name = simpledialog.askstring(" ", "Set the name:", initialvalue=default_name)
            if new_name:
                new_box = source.copy()
                new_box['name'] = new_name
                new_box['locked'] = False
                new_box['x'] = min(new_box['x'] + 1, self.width - new_box['w'])
                new_box['y'] = min(new_box['y'] + 1, self.height - new_box['h'])
                self.boxes.append(new_box)
                self.display_sheet()

    def cycle_palette_up(self, e):
        if self.active_box_idx is not None:
            b = self.boxes[self.active_box_idx]
            if b['clut_global_idx'] < len(self.all_palettes)-1: b['clut_global_idx']+=1; self.display_sheet()

    def cycle_palette_down(self, e):
        if self.active_box_idx is not None:
            b = self.boxes[self.active_box_idx]
            if b['clut_global_idx'] > 0: b['clut_global_idx']-=1; self.display_sheet()

    def handle_mousewheel(self, event):
        delta = -1 if (event.num == 4 or event.delta > 0) else 1
        if event.state & 0x0004: # Ctrl
            self.zoom = max(0.5, min(self.zoom * (1.1 if delta < 0 else 0.9), 30.0))
            self.display_sheet()
        elif event.state & 0x0001: # Shift
            self.canvas.xview_scroll(delta, "units")
        else:
            self.canvas.yview_scroll(delta, "units")

    def get_snapped_pixel(self, ex, ey):
        rx, ry = self.canvas.canvasx(ex)/self.zoom, self.canvas.canvasy(ey)/self.zoom
        return int(max(0, min(rx, self.width))), int(max(0, min(ry, self.height)))

    def create_checkerboard(self, w, h, size=4):
        c1, c2 = "#8f8f8f", "#bfbfbf"
        bg = Image.new("RGBA", (w, h), c1)
        draw = ImageDraw.Draw(bg)
        for y in range(0, h, size):
            for x in range(0, w, size):
                if (x // size + y // size) % 2 == 0: draw.rectangle([x, y, x + size - 1, y + size - 1], fill=c2)
        return bg
        
    def convert_png_to_tim(self):
        """Dispatcher for PNG to TIM conversion (Single vs Bulk)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("PNG to TIM")
        width, height = 408, 216
        pos_x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        pos_y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.transient(self.root)
        dialog.focus_set()
        dialog.grab_set()

        var = tk.StringVar(value="single")
        tk.Label(dialog, text="Select Conversion Mode:", font=("Arial", 10, "bold")).pack(pady=10)
        
        tk.Radiobutton(dialog, variable=var, value="single", justify=tk.LEFT, wraplength=350,
                       text="Single PNG: Amount of colors will be checked and prompt you to select the target bit depth.").pack(anchor="w", padx=20, pady=5)
        
        tk.Radiobutton(dialog, variable=var, value="bulk", justify=tk.LEFT, wraplength=350,
                       text="Folder: Bulk process. Bit depth for each image is set automatically based on color count. A log will be generated showing the targeted bit depth for each file.").pack(anchor="w", padx=20, pady=5)

        state = {"action": "cancel"}
        def ok(): state["action"] = "ok"; dialog.destroy()
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="OK", command=ok, width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=10)

        self.root.wait_window(dialog)
        if state["action"] != "ok": return

        if var.get() == "single":
            self._process_single_png_to_tim()
        else:
            self.bulk_png_to_tim()

    def bulk_png_to_tim(self):
        """Processes a folder of PNGs with mandatory reporting even if all fail"""
        src = filedialog.askdirectory(title="Select Folder of PNGs")
        if not src: return
        dest = filedialog.askdirectory(title="Select Output Folder")
        if not dest: return

        files = [f for f in os.listdir(src) if f.lower().endswith(".png")]
        if not files:
            messagebox.showinfo("Bulk Import", "No .png files found in the source directory.")
            return

        dialog, pb, lbl = self.create_progress_dialog("Converting PNGs...", len(files))

        def worker():
            success_count = 0
            details, failed = [], []

            for i, f_name in enumerate(files):
                self.root.after(0, lambda v=i, f=f_name: [pb.configure(value=v), lbl.configure(text=f"Encoding: {f}")])
                
                try:
                    img = Image.open(os.path.join(src, f_name)).convert("RGBA")
                    unique_colors = []
                    for y in range(img.height):
                        for x in range(img.width):
                            p = img.getpixel((x, y))
                            if p not in unique_colors: unique_colors.append(p)
                            
                    # Sort the colors in the palette. Doesn't matter what order exactly but just needs AN order. Needed for the tachometers in game_status_files
                    unique_colors.sort(key=lambda p: (p[3], 0.299*p[0] + 0.587*p[1] + 0.114*p[2]))
                    
                    count = len(unique_colors)
                    # Helper
                    mode = 8 if count <= 16 else (9 if count <= 256 else 2)
                    depth_str = "4bpp" if mode == 8 else ("8bpp" if mode == 9 else "16bpp")
                    
                    tim_data = self._build_tim_bytes(img, unique_colors, mode)
                    
                    with open(os.path.join(dest, os.path.splitext(f_name)[0] + ".tim"), "wb") as f:
                        f.write(tim_data)
                    
                    details.append(f"{depth_str} with {count} colors: {f_name}")
                    success_count += 1
                except Exception as e:
                    failed.append(f"{f_name} (Error: {str(e)})")

            # Detailed report
            self.root.after(0, lambda: [
                dialog.destroy(), 
                self.show_detailed_bulk_report(success_count, details, failed)
            ])
            messagebox.showinfo("Done", "Process finished.\nSee log for details.")
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def show_detailed_bulk_report(self, success_count, details, failed):
        """Generates a detailed scrollable report of color counts and bit depths"""
        report = []
        report.append(f"=== Bulk PNG to TIM Report ===")
        report.append(f"Successfully processed {success_count} files.\n")
        
        if details:
            report.append("--- Conversion Log ---")
            report.extend(details)
            report.append("") # Spacer

        if failed:
            report.append("--- Failed/Skipped ---")
            report.extend(failed)

        self.show_scrollable_report("Bulk Conversion Details", "\n".join(report))

    def show_bulk_report(self, success, failed):
        """Standardized report display"""
        report = f"Operation Complete.\nSuccessfully processed {success} files.\n"
        if failed:
            report += f"\nFailed ({len(failed)}):\n" + "\n".join(failed)
        
        if len(failed) > 10:
            self.show_scrollable_report("Process Report", report)
        else:
            messagebox.showinfo("Result", report)

    def _build_tim_bytes(self, img, colors, mode):
        """Helper to build TIM bytearray"""
        out = bytearray(struct.pack("<II", 0x10, mode))
        if mode in [8, 9]:
            limit = 16 if mode == 8 else 256
            p_colors = colors[:limit]
            while len(p_colors) < limit: p_colors.append((0,0,0,0))
            
            clut = bytearray()
            for r, g, b, a in p_colors:
                if (a <= 4):
                    r5, g5, b5, stp = 0, 0, 0, 0 # clean pixels to not enough opacity to survive crunch, or blank pixels
                elif (a <= 7) and (a >= 5):
                    a = 8 # round up to 8
                else:
                    stp = 1 if (a < 255) else 0 # 1-254 is stp, 255 is opaque
                    rf, gf, bf = (r*a)//255, (g*a)//255, (b*a)//255 # black-key transparency
                    r5, g5, b5 = rf>>3, gf>>3, bf>>3 # crunch to 5 bits
                clut.extend(struct.pack("<H", (stp<<15)|(b5<<10)|(g5<<5)|r5))
            
            out.extend(struct.pack("<IHHHH", len(clut)+12, 0, 0, len(p_colors), 1) + clut)
            cmap = {c: i for i, c in enumerate(p_colors)}
            pix = bytearray()
            if mode == 8:
                for y in range(img.height):
                    for x in range(0, img.width, 2):
                        i1, i2 = cmap.get(img.getpixel((x,y)),0), cmap.get(img.getpixel((x+1,y)),0)
                        pix.append(((i2&0x0F)<<4)|(i1&0x0F))
                h_w = img.width // 4
            else:
                for y in range(img.height):
                    for x in range(img.width): pix.append(cmap.get(img.getpixel((x,y)), 0))
                h_w = img.width // 2
            out.extend(struct.pack("<IHHHH", len(pix)+12, 0, 0, h_w, img.height) + pix)
        else:
            pix = bytearray()
            for y in range(img.height):
                for x in range(img.width):
                    r,g,b,a = img.getpixel((x,y))
                    if (a <= 4):
                        r5, g5, b5, stp = 0, 0, 0, 0 # clean pixels to not enough opacity to survive crunch
                    elif (a <= 7) and (a >= 5):
                        a = 8 # round up to 8
                    else:
                        stp = 1 if (a < 255) else 0 # 1-254 is stp, 255 is opaque
                        rf, gf, bf = (r*a)//255, (g*a)//255, (b*a)//255 # black-key transparency
                        r5, g5, b5 = rf>>3, gf>>3, bf>>3 # crunch to 5 bits
                    pix.extend(struct.pack("<H", (stp<<15)|(b5<<10)|(g5<<5)|r5))
            out.extend(struct.pack("<IHHHH", len(pix)+12, 0, 0, img.width, img.height) + pix)
        return out

    def _process_single_png_to_tim(self):
        path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if not path: return
        img = Image.open(path).convert("RGBA")
        
        # Determine unique colors
        unique_colors = []
        for y in range(img.height):
            for x in range(img.width):
                p = img.getpixel((x, y))
                if p not in unique_colors: unique_colors.append(p)
                
        # Sort the colors in the palette. Doesn't matter what order exactly but just needs AN order. Needed for the tachometers in game_status_files
        unique_colors.sort(key=lambda p: (p[3], 0.299*p[0] + 0.587*p[1] + 0.114*p[2]))
        
        color_count = len(unique_colors)
        
        # Create Mode Selector Dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Target Format")
        width, height = 350, 260
        pos_x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        pos_y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text=f"Colors detected: {color_count}", font=("Arial", 10, "bold")).pack(pady=10)
        
        # Logic to suggest the best mode based on color count
        if color_count <= 16: default_val = 8 # 4bpp
        elif color_count <= 256: default_val = 9 # 8bpp
        else: default_val = 2 # 16bpp

        var = tk.IntVar(value=default_val)
        
        # --- 4bpp Option ---
        rb4 = tk.Radiobutton(dialog, text=f"4bpp (Max 16 colors)", variable=var, value=8)
        rb4.pack(anchor="w", padx=50, pady=2)
        if color_count > 16:
            rb4.config(state=tk.DISABLED, fg="gray")
            tk.Label(dialog, text="   (Exceeds color limit)", fg="red", font=("Arial", 8)).pack(anchor="w", padx=70)

        # --- 8bpp Option ---
        rb8 = tk.Radiobutton(dialog, text=f"8bpp (Max 256 colors)", variable=var, value=9)
        rb8.pack(anchor="w", padx=50, pady=2)
        if color_count > 256:
            rb8.config(state=tk.DISABLED, fg="gray")
            tk.Label(dialog, text="   (Exceeds color limit)", fg="red", font=("Arial", 8)).pack(anchor="w", padx=70)

        # --- 16bpp Option ---
        tk.Radiobutton(dialog, text="16bpp (High Color / Direct)", variable=var, value=2).pack(anchor="w", padx=50, pady=2)

        state = {"action": "cancel"}
        def ok(): 
            state["action"] = "ok"
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Convert", command=ok, width=12).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=10)

        self.root.wait_window(dialog)
        if state["action"] != "ok": return

        # Final Processing
        out_path = filedialog.asksaveasfilename(defaultextension=".tim")
        if not out_path: return
        
        mode = var.get()
        tim_data = self._build_tim_bytes(img, unique_colors, mode)
        
        with open(out_path, "wb") as f: 
            f.write(tim_data)
        
        messagebox.showinfo("Success", "TIM created successfully.")
        
    def bulk_tim_to_png(self):
        """Processes a directory of TIMs"""
        src_dir = filedialog.askdirectory(title="Select Folder containing Tim files")
        if not src_dir: return
        dest_dir = filedialog.askdirectory(title="Select Destination Folder")
        if not dest_dir: return

        files = [f for f in os.listdir(src_dir) if f.lower().endswith(".tim")]
        if not files:
            messagebox.showinfo("Bulk Export", "No .tim files found in the source directory.")
            return

        dialog, pb, lbl = self.create_progress_dialog("Converting TIMs...", len(files))
        
        def worker():
            success, failed = 0, []
            for i, filename in enumerate(files):
                self.root.after(0, lambda v=i, f=filename: [pb.configure(value=v), lbl.configure(text=f"Processing: {f}")])
                
                try:
                    with open(os.path.join(src_dir, filename), "rb") as f:
                        data = f.read()

                    # Skip texture sheets
                    if data[4:8] == b"\x00\x00\x00\x00":
                        failed.append(f"{filename} is a texture sheet. (GT2 Sheet)")
                        continue

                    mode = struct.unpack("<I", data[4:8])[0]
                    if mode in [8, 9]:
                        if struct.unpack("<H", data[18:20])[0] > 1:
                            failed.append(f"{filename} is a texture sheet. (Multi-CLUT Standard Tim)")
                            continue

                    # Conversion
                    if mode == 8:
                        w, h, indices, pals = self._bulk_parse_std_16(data)
                        img = Image.new("RGBA", (w, h))
                        img.putdata([pals[0][idx] for idx in indices])
                    elif mode == 9:
                        w, h, indices, pals = self._bulk_parse_std_256(data)
                        img = Image.new("RGBA", (w, h))
                        img.putdata([pals[0][idx] for idx in indices])
                    elif mode == 2:
                        w, h, rgba = self._bulk_parse_std_true(data)
                        img = Image.new("RGBA", (w, h))
                        img.putdata(rgba)
                    else:
                        failed.append(f"{filename} is not a standard Tim file.")
                        continue

                    img.save(os.path.join(dest_dir, filename.replace(".tim", ".png")))
                    success += 1
                except Exception as e:
                    failed.append(f"{filename} (Error: {str(e)})")

            # Report
            self.root.after(0, lambda: [dialog.destroy(), self.show_bulk_report(success, failed)])

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def show_scrollable_report(self, title, text):
        """Utility to show long error lists in a proper window"""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("500x400")
        txt_area = tk.Text(win, padx=10, pady=10)
        txt_area.insert("1.0", text)
        txt_area.config(state=tk.DISABLED)
        txt_area.pack(fill=tk.BOTH, expand=True)
        tk.Button(win, text="Close", command=win.destroy).pack(pady=5)
        
    def ask_build_mode(self, title, description_no_header):
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title("Export Options")
        width, height = 450, 160
        pos_x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        pos_y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.deiconify()
        dialog.transient(self.root)
        dialog.focus_set()
        dialog.grab_set()
        var = tk.StringVar(value="sheet")            
        tk.Label(dialog, text="Select Build Mode:", font=("Arial", 10, "bold")).pack(pady=10)
        tk.Radiobutton(dialog, text="Normal: Standard TIM File", variable=var, value="normal").pack(anchor="w", padx=20)
        tk.Radiobutton(dialog, text=f"No-header: {description_no_header}", variable=var, value="noheader").pack(anchor="w", padx=20)
        var.set("normal")

        res = {"mode": None}
        def ok(): res["mode"] = var.get(); dialog.destroy()
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Build", command=ok, width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side=tk.LEFT, padx=10)

        self.root.wait_window(dialog)
        return res["mode"]

    def export_png_dialog(self):
        if self.raw_data is None: return
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title("Export Options")
        width, height = 450, 220
        pos_x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        pos_y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.deiconify()
        dialog.transient(self.root)
        dialog.focus_set()
        dialog.grab_set()
        var = tk.StringVar(value="sheet")
        tk.Label(dialog, text="Select Export Method:", font=("Arial", 10, "bold")).pack(pady=10)
        tk.Radiobutton(dialog, variable=var, value="sheet", wraplength=400, justify=tk.LEFT,
                       text="Sheet Project Folder: Outputs PNG images and saves\nthe current state of the CLUT view to a .json file. (For Texture sheets)").pack(anchor="w", padx=20, pady=5)
        tk.Radiobutton(dialog, variable=var, value="single", wraplength=400, justify=tk.LEFT,
                       text="Single PNG: Outputs a single PNG of the entire canvas.\n(For single Tim images)").pack(anchor="w", padx=20, pady=5)
        state = {"action": "cancel"}
        def ok(): 
            state["action"] = "ok"
            dialog.destroy()
        tk.Button(dialog, text="OK", command=ok, width=12).pack(side=tk.LEFT, padx=50, pady=10)
        tk.Button(dialog, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.RIGHT, padx=50, pady=10)
        self.root.wait_window(dialog)
        if state["action"] != "ok": return
        if var.get() == "sheet":
            folder = filedialog.askdirectory(title="Select Output Folder")
            if not folder: return
            for b in self.boxes:
                pal = self.all_palettes[b['clut_global_idx']]
                out = Image.new("RGBA", (b['w'], b['h']))
                pix = [pal[self.pixel_indices[py*self.width+px]] for py in range(b['y'], b['y']+b['h']) for px in range(b['x'], b['x']+b['w'])]
                out.putdata(pix); out.save(os.path.join(folder, f"{b['name']}.png"))
            with open(os.path.join(folder, "config.json"), "w") as f: json.dump({"canvas": {"width": self.width, "height": self.height}, "textures": self.boxes}, f, indent=4)
            messagebox.showinfo("Export", "Sheet project folder created.")
        else:
            path = filedialog.asksaveasfilename(defaultextension=".png")
            if not path: return
            out = Image.new("RGBA", (self.width, self.height))
            if self.tim_type == 2: out.putdata(self.true_color_data)
            else: out.putdata([self.all_palettes[self.global_default_idx][i] for i in self.pixel_indices])
            out.save(path)
            messagebox.showinfo("Export", "Single PNG exported.")

    def build_gt2_tim_sheet(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path: return
        
        mode = self.ask_build_mode("Build 4bpp GT2 Tim Sheet", "A special format for GT2's iconimg.dat file")
        if not mode: return

        out_path = filedialog.asksaveasfilename(defaultextension=".tim", title="Specify Output TIM File")
        if not out_path: return

        with open(path, "r") as f: 
            data = json.load(f)
        
        cw, ch, folder = data["canvas"]["width"], data["canvas"]["height"], os.path.dirname(path)
        
        max_clut_idx = 0
        for tex in data["textures"]:
            idx = tex.get("clut_global_idx", 0)
            if idx > max_clut_idx: max_clut_idx = idx
        
        num_palettes = ((max_clut_idx // 4) + 1) * 4
        clut_data_size = num_palettes * 32
        clut_block = bytearray(clut_data_size)
        
        prepared = []
        for tex in data["textures"]:
            img_path = os.path.join(folder, f"{tex['name']}.png")
            if not os.path.exists(img_path): continue
            img = Image.open(img_path).convert("RGBA")
            colors = []
            for y in range(img.height):
                for x in range(img.width):
                    p = img.getpixel((x, y))
                    if p not in colors: colors.append(p)
                    
            # Sort the colors in the palette. Doesn't matter what order exactly but just needs AN order. Needed for the tachometers in game_status_files
            colors.sort(key=lambda p: (p[3], 0.299*p[0] + 0.587*p[1] + 0.114*p[2]))
            
            if len(colors) > 16:
                messagebox.showerror("Color Limit", f"'{tex['name']}' has {len(colors)} colors.")
                return 

            prepared.append({'meta': tex, 'img': img, 'cmap': {c: i for i, c in enumerate(colors)}})
            c_idx = tex.get("clut_global_idx", 0)
            offset = c_idx * 32
            
            for i, (r, g, b, a) in enumerate(colors):
                if i >= 16: break
                if (a <= 4):
                    r5, g5, b5, stp = 0, 0, 0, 0 # clean pixels to not enough opacity to survive crunch
                elif (a <= 7) and (a >= 5):
                    a = 8 # round up to 8
                else:
                    stp = 1 if (a < 255) else 0 # 1-254 is stp, 255 is opaque
                    
                rf, gf, bf = (r*a)//255, (g*a)//255, (b*a)//255 # black-key transparency
                r5, g5, b5 = rf>>3, gf>>3, bf>>3 # crunch to 5 bits
                clut_block[offset + (i*2) : offset + (i*2) + 2] = struct.pack("<H", (stp<<15)|(b5<<10)|(g5<<5)|r5)

        #4. Build Pixel Data
        pix_chunk = bytearray((cw // 2) * ch)
        touched_mask = [False] * (cw * ch)
        for y in range(ch):
            for x in range(0, cw, 2):
                # Initialize pixels to all bits on. Replicates original binary data
                i1 = i2 = 0x0F
                
                # Check for first pixel in pair (x)
                for pt in prepared:
                    m = pt['meta']
                    if m['x'] <= x < m['x']+m['w'] and m['y'] <= y < m['y']+m['h']:
                        # Check if we wrote the index already. Overlapping CLUTs are rare, but basically the 1st layer has to define the indices for all layers including itself. The other CLUT layers merely provide a different palette.
                        # Overlapping CLUTs require that the pixel indices from the 1st layer also work for them too. Seen in game_status_files's BA bars.
                        if not touched_mask[y * cw + x]:
                            local_x, local_y = x - m['x'], y - m['y']
                            # Safety check against actual source image dimensions
                            if local_x < pt['img'].width and local_y < pt['img'].height:
                                i1 = pt['cmap'].get(pt['img'].getpixel((local_x, local_y)), 0)
                                touched_mask[y * cw + x] = True
                
                # Check for second pixel in pair (x+1)
                for pt in prepared:
                    m = pt['meta']
                    if m['x'] <= (x + 1) < m['x']+m['w'] and m['y'] <= y < m['y']+m['h']:
                        # Check if we wrote the index already. Overlapping CLUTs are rare, but basically the 1st layer has to define the indices for all layers including itself. The other CLUT layers merely provide a different palette.
                        # Overlapping CLUTs require that the pixel indices from the 1st layer also work for them too. Seen in game_status_files's BA bars.
                        if not touched_mask[y * cw + (x + 1)]:
                            local_x, local_y = (x + 1) - m['x'], y - m['y']
                            # Safety check against actual source image dimensions
                            if local_x < pt['img'].width and local_y < pt['img'].height:
                                i2 = pt['cmap'].get(pt['img'].getpixel((local_x, local_y)), 0)
                                touched_mask[y * cw + (x + 1)] = True
                        
                pix_chunk[(y * (cw // 2)) + (x // 2)] = ((i2 & 0x0F) << 4) | (i1 & 0x0F)
        
        start_replace = len(pix_chunk) - len(clut_block)
        if start_replace < 0:
            messagebox.showerror("Error", "Sheet too small for CLUTs.")
            return
            
        pix_chunk[start_replace:] = clut_block
        header = b'\x10\x00\x00\x00\x00\x00\x00\x00' + struct.pack("<I", 12+len(pix_chunk)) + \
                 b'\x00'*4 + struct.pack("<H", cw//4) + struct.pack("<H", ch)
        full_data = header + pix_chunk
        if mode == "noheader": full_data = full_data[0x14:]

        with open(out_path, "wb") as f: f.write(full_data)
        messagebox.showinfo("Success", "Build complete.")

    def build_standard_tim_sheet(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path: return
        
        # 1. Selection Dialog for Format
        dialog = tk.Toplevel(self.root)
        dialog.title("Build Options")
        width, height = 365, 220
        pos_x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (width // 2)
        pos_y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.focus_set()

        tk.Label(dialog, text="Select Sheet Format:", font=("Arial", 10, "bold")).pack(pady=10)
        
        # 8=Std 4bpp, 9=Std 8bpp, 0=Special GT2
        mode_var = tk.IntVar(value=8) 
        tk.Radiobutton(dialog, text="Standard 4bpp (16 colors/pal)", variable=mode_var, value=8).pack(anchor="w", padx=10)
        tk.Radiobutton(dialog, text="Standard 8bpp (256 colors/pal)", variable=mode_var, value=9).pack(anchor="w", padx=10)
        tk.Radiobutton(dialog, text="4bpp Headerless: A special format for GT2's racefont.dat file", variable=mode_var, value=0).pack(anchor="w", padx=10)
        
        state = {"action": "cancel"}
        def ok(): state["action"] = "ok"; dialog.destroy()
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Build Sheet", command=ok, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12).pack(side=tk.LEFT, padx=5)
        
        self.root.wait_window(dialog)
        if state["action"] != "ok": return

        # 2. Setup Constants
        selected_mode = mode_var.get()
        is_8bpp = (selected_mode == 9)
        clut_limit = 256 if is_8bpp else 16
        # 8bpp uses 0xFF padding, 4bpp (Std and GT2) uses 0x0F
        pad_val = 0xFF if is_8bpp else 0x0F

        out_path = filedialog.asksaveasfilename(defaultextension=".tim")
        if not out_path: return

        # 3. Load Project and Prepare Images
        with open(path, "r") as f: data = json.load(f)
        cw, ch, folder = data["canvas"]["width"], data["canvas"]["height"], os.path.dirname(path)
        
        # FIND THE HIGHEST INDEX WITHOUT PADDING TO MULTIPLES OF 4
        max_clut_idx = 0
        for tex in data["textures"]:
            idx = tex.get("clut_global_idx", 0)
            if idx > max_clut_idx: max_clut_idx = idx
        
        # EXACT PALETTE COUNT
        num_palettes = max_clut_idx + 1 
        clut_block = bytearray(num_palettes * clut_limit * 2)
        prepared = []
        
        for tex in data["textures"]:
            img_path = os.path.join(folder, f"{tex['name']}.png")
            if not os.path.exists(img_path): continue
            img = Image.open(img_path).convert("RGBA")
            colors = []
            for y in range(img.height):
                for x in range(img.width):
                    p = img.getpixel((x, y))
                    if p not in colors: colors.append(p)
                    
            # Sort the colors in the palette. Doesn't matter what order exactly but just needs AN order. Needed for the tachometers in game_status_files
            colors.sort(key=lambda p: (p[3], 0.299*p[0] + 0.587*p[1] + 0.114*p[2]))
            
            if len(colors) > clut_limit:
                messagebox.showerror("Limit Error", f"'{tex['name']}' exceeds {clut_limit} colors.")
                return

            prepared.append({'meta': tex, 'img': img, 'cmap': {c: i for i, c in enumerate(colors)}})
            
            c_idx = tex.get("clut_global_idx", 0)
            offset = c_idx * (clut_limit * 2)
            for i, (r, g, b, a) in enumerate(colors):
                if i >= 16: break
                if (a <= 4):
                    r5, g5, b5, stp = 0, 0, 0, 0 # clean pixels that don't have enough opacity to survive crunch
                elif (a <= 7) and (a >= 5):
                    a = 8 # round up to 8
                else:
                    stp = 1 if (a < 255) else 0 # 1-254 is stp, 255 is opaque
                    rf, gf, bf = (r*a)//255, (g*a)//255, (b*a)//255 # black-key transparency
                    r5, g5, b5 = rf>>3, gf>>3, bf>>3 # crunch to 5 bits
                struct.pack_into("<H", clut_block, offset + (i*2), (stp << 15) | (b5 << 10) | (g5 << 5) | r5)

        # 4. Build Pixel Data
        px_bytes = bytearray()
        touched_mask = [False] * (cw * ch) # Track written pixels across both 8bpp and 4bpp modes

        if is_8bpp:
            for y in range(ch):
                for x in range(cw):
                    idx = pad_val
                    for pt in prepared:
                        m = pt['meta']
                        # Check if this pixel falls inside this texture's bounding box region
                        if m['x'] <= x < m['x']+m['w'] and m['y'] <= y < m['y']+m['h']:
                            if not touched_mask[y * cw + x]:
                                # Base layer claims ownership of this coordinate
                                touched_mask[y * cw + x] = True
                                
                                local_x, local_y = x - m['x'], y - m['y']
                                if local_x < pt['img'].width and local_y < pt['img'].height:
                                    idx = pt['cmap'].get(pt['img'].getpixel((local_x, local_y)), 0)
                                else:
                                    idx = 0 # Fallback safe index inside the box if image dimensions fall short

                    px_bytes.append(idx & 0xFF)
            h_w = cw // 2 
        else:
            for y in range(ch):
                for x in range(0, cw, 2):
                    i1 = i2 = pad_val
                    
                    # Check for first pixel in pair (x)
                    for pt in prepared:
                        m = pt['meta']
                        if m['x'] <= x < m['x']+m['w'] and m['y'] <= y < m['y']+m['h']:
                            if not touched_mask[y * cw + x]:
                                touched_mask[y * cw + x] = True
                                
                                local_x, local_y = x - m['x'], y - m['y']
                                if local_x < pt['img'].width and local_y < pt['img'].height:
                                    i1 = pt['cmap'].get(pt['img'].getpixel((local_x, local_y)), 0)
                                else:
                                    i1 = 0

                    # Check for second pixel in pair (x+1)
                    for pt in prepared:
                        m = pt['meta']
                        if m['x'] <= x+1 < m['x']+m['w'] and m['y'] <= y < m['y']+m['h']:
                            if not touched_mask[y * cw + (x + 1)]:
                                touched_mask[y * cw + (x + 1)] = True
                                
                                local_x, local_y = (x + 1) - m['x'], y - m['y']
                                if local_x < pt['img'].width and local_y < pt['img'].height:
                                    i2 = pt['cmap'].get(pt['img'].getpixel((local_x, local_y)), 0)
                                else:
                                    i2 = 0
                                    
                    px_bytes.append(((i2 & 0x0F) << 4) | (i1 & 0x0F))
            h_w = cw // 4

        # 5. Assemble Final Buffer
        if selected_mode == 0:
            # --- GT2 Special Mode 0 (Standard TIM Variant) ---
            # Main Header (20 bytes / 0x14)
            # Standard TIMs usually have block headers, but we are skipping them here.
            
            full_file_size = 20 + len(clut_block) + len(px_bytes)
            
            buf = bytearray()

            # DATA SEGMENT: CLUT then Pixels, NO block headers.
            buf.extend(clut_block)
            buf.extend(px_bytes)
            
        else:
            # --- Standard TIM Logic (Modes 8 and 9) ---
            buf = bytearray(struct.pack("<II", 0x10, selected_mode))
            
            # Standard Palette Block (12-byte Header + Data)
            buf.extend(struct.pack("<IHHHH", len(clut_block) + 12, 0, 0, clut_limit, num_palettes))
            buf.extend(clut_block)
            
            # Standard Pixel Block (12-byte Header + Data)
            buf.extend(struct.pack("<IHHHH", len(px_bytes) + 12, 0, 0, h_w, ch))
            buf.extend(px_bytes)

        # Final write
        with open(out_path, "wb") as f: 
            f.write(buf)

        with open(out_path, "wb") as f: f.write(buf)
        messagebox.showinfo("Success", "Sheet built successfully.")
        
    def parse_trp(self, data, count):
        """Scans raw data for TIM signatures and dispatches to appropriate parsers"""
        magics = [
            #b"\x10\x00\x00\x00\x00\x00\x00\x00", # GT2/PD 4bpp // I don't think this format is possible with this container format, that's probably why the multi tims that have these use an offset list
            b"\x10\x00\x00\x00\x08\x00\x00\x00", # Std 4bpp
            b"\x10\x00\x00\x00\x09\x00\x00\x00", # Std 8bpp
            b"\x10\x00\x00\x00\x02\x00\x00\x00"  # Std TrueColor
        ]
        
        found_offsets = []
        # Scan the file for standard TIM magics
        for m in magics:
            start = 0
            while True:
                idx = data.find(m, start)
                if idx == -1: break
                found_offsets.append((idx, m))
                start = idx + 8 # Continue searching

        # Sort by offset to process them in order
        found_offsets.sort()
        detected_count = len(found_offsets)

        if detected_count == 0:
            messagebox.showwarning("Scan Result", "No TIM signatures detected in the TRP / BSP data.")
            return
            
        dest = filedialog.askdirectory(title="Select Extraction Folder")
        if not dest: return

        for i, (off, magic) in enumerate(found_offsets):
            # Determine end of file
            end_off = found_offsets[i+1][0] if i+1 < detected_count else len(data)
            chunk = data[off:end_off]
            
            ext = ".tim"
            filename = os.path.join(dest, f"{i:03d}_extracted{ext}")
            
            with open(filename, "wb") as f:
                f.write(chunk)

        if detected_count < count:
            messagebox.showinfo("Success", f"Extracted {detected_count} files, but TRP's header reported {count} files. \n There may be other file types in this package.")
        elif detected_count > count:
            messagebox.showinfo("Success", f"Extracted {detected_count} files, but TRP's header reported {count} files.")
        else:
            messagebox.showinfo("Success", f"Extracted {detected_count} files.")

    def parse_multi_tim(self, data, count):
        dest = filedialog.askdirectory(); offs = [struct.unpack("<I", data[(i+1)*4:(i+2)*4])[0] for i in range(count)] + [len(data)]
        for i in range(count):
            c = data[offs[i]:offs[i+1]]
            if c.startswith(b"\x10\x00\x00\x00"):
                with open(os.path.join(dest, f"{i:03d}_extracted.tim"), "wb") as f: f.write(c)
        messagebox.showinfo("Success", f"Extracted {i+1} files.")
                
    def parse_multi_file(self, data, count):
        dest = filedialog.askdirectory(); offs = [struct.unpack("<I", data[(i+1)*4:(i+2)*4])[0] for i in range(count)] + [len(data)]
        for i in range(count):
            c = data[offs[i]:offs[i+1]]
            with open(os.path.join(dest, f"{i:03d}_extracted"), "wb") as f: f.write(c)
        messagebox.showinfo("Success", f"Extracted {i+1} files.")
        
    def build_multi_tim_container(self):
        src = filedialog.askdirectory()
        if not src: return 
        try: tims = sorted([f for f in os.listdir(src) if f.lower().endswith(".tim")])
        except OSError: return

        if not tims:
            messagebox.showwarning("No Files", "No .tim files found in the selected folder.")
            return
        h_size = 4 + (len(tims)*4); out = bytearray(struct.pack("<I", len(tims)) + b'\x00'*(len(tims)*4))
        curr = h_size
        for i, f in enumerate(tims):
            with open(os.path.join(src, f), "rb") as rb: b = rb.read()
            struct.pack_into("<I", out, 4+(i*4), curr); out.extend(b); curr += len(b)
        save = filedialog.asksaveasfilename()
        if save: 
            with open(save, "wb") as f: f.write(out)
        messagebox.showinfo("Success", f"Packed {i+1} files.")
        
    def build_trp_container(self):
        """Packs .tim files into the .trp container format, guards against non-standard formats becuase they seem to only contain standard Tim files"""
        src = filedialog.askdirectory(title="Select Folder to Pack into TRP / BSP")
        if not src: 
            return 
            
        try: 
            tims = sorted([f for f in os.listdir(src) if f.lower().endswith(".tim")])
        except OSError: 
            return

        if not tims:
            messagebox.showwarning("No Files", "No .tim files found in the selected folder.")
            return

        # --- Format Validation Guard ---
        # Valid Standard Magics: 0x08 (4bpp), 0x09 (8bpp), 0x02 (TrueColor)
        valid_standard_modes = [2, 8, 9]
        invalid_files = []

        for f_name in tims:
            with open(os.path.join(src, f_name), "rb") as f:
                header = f.read(8)
                if len(header) < 8:
                    invalid_files.append(f"{f_name} (Corrupt/Empty)")
                    continue
                
                # Check magic (0x10) and then the mode
                magic, mode = struct.unpack("<II", header)
                if magic != 0x10 or mode not in valid_standard_modes:
                    if mode == 0:
                        invalid_files.append(f"{f_name} (Pixel mode {mode}: GT2 Sheet)")
                    else:
                        invalid_files.append(f"{f_name} (Not a texture file)")

        if invalid_files:
            warn_msg = "The following files are not the expected Standard TIM format:\n\n"
            warn_msg += "\n".join(invalid_files[:10]) # Show first 10
            if len(invalid_files) > 10:
                warn_msg += f"\n...and {len(invalid_files) - 10} more."
            warn_msg += "\n\nDo you want to pack this?"
            
            if not messagebox.askyesno("Format Warning", warn_msg):
                return

        # --- Packing ---
        out = bytearray(struct.pack("<I", len(tims)))
        
        for f_name in tims:
            try:
                with open(os.path.join(src, f_name), "rb") as rb: 
                    out.extend(rb.read())
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read {f_name}: {e}")
                return

        save = filedialog.asksaveasfilename(
            defaultextension=".trp", 
            title="Save TRP / BSP Container",
            filetypes=[("TRP / BSP Container", "*.trp", "*.bsp")]
        )
        
        if save: 
            try:
                with open(save, "wb") as f: 
                    f.write(out)
                messagebox.showinfo("Success", f"Packed {len(tims)} files into TRP.")
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not write file: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    PDTimTool(root)
    root.mainloop()