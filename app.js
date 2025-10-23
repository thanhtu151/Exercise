// Render word bank
const bank = document.getElementById("bank");
WORD_BANK.forEach(w => {
  const t = document.createElement("span");
  t.className = "tag"; t.textContent = w;
  bank.appendChild(t);
});

const page = document.getElementById("page");

// Tạo các ô theo toạ độ %
FIELDS.forEach(f => {
  const wrap = document.createElement("div");
  wrap.className = "input-box";
  wrap.style.left = f.left + "%";
  wrap.style.top  = f.top  + "%";
  wrap.style.width = f.width + "%";

  const inp = document.createElement("input");
  inp.id = f.id;
  inp.placeholder = "write here";
  if (f.locked) { inp.value = f.answer; inp.disabled = true; }
  wrap.appendChild(inp);
  page.appendChild(wrap);
});

// Chuẩn hoá so sánh
function norm(s){ return (s||"").trim().toLowerCase().replace(/\s+/g,' '); }

// Nút check
document.getElementById("check").onclick = () => {
  let correct = 0, total = 0;
  FIELDS.forEach(f => {
    if (f.locked) return; // bỏ qua ví dụ có sẵn
    total++;
    const wrap = document.getElementById(f.id).parentElement;
    wrap.classList.remove("correct","wrong");
    const val = document.getElementById(f.id).value;
    if (norm(val) === norm(f.answer)) {
      wrap.classList.add("correct"); correct++;
    } else {
      wrap.classList.add("wrong");
    }
  });
  document.getElementById("score").textContent = `Score: ${correct}/${total}`;
};

// Nút clear
document.getElementById("clear").onclick = () => {
  FIELDS.forEach(f => {
    if (f.locked) return;
    const el = document.getElementById(f.id);
    el.value = "";
    el.parentElement.classList.remove("correct","wrong");
  });
  document.getElementById("score").textContent = "";
};
