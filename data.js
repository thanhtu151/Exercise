// Word bank hiện ở dưới (tham khảo từ trang đề)
const WORD_BANK = [
  "maths","a hotel","wool","a rucksack","silver","a tent","soap","a factory",
  "a brush","glue","a dictionary","a museum" // thêm cho đủ 10 câu
];

// Vị trí 10 ô điền (ví dụ ước lượng – bạn chỉnh lại cho khớp ảnh của bạn)
const FIELDS = [
  // example của đề thường đã điền sẵn -> có thể bỏ qua hoặc để disabled
  // { id: "ex", left: 78, top: 23, width: 28, answer: "a hotel", locked: true },

  { id: "q1", left: 77, top: 36.5, width: 26, answer: "glue" },        // hold things together
  { id: "q2", left: 77, top: 48.0, width: 26, answer: "a rucksack" },  // bag on your back
  { id: "q3", left: 77, top: 59.5, width: 26, answer: "a brush" },     // make your hair tidy
  { id: "q4", left: 77, top: 71.0, width: 26, answer: "a tent" },      // sleep when camping
  { id: "q5", left: 77, top: 82.5, width: 26, answer: "soap" },        // use to wash

  // nếu trang đó có 10 câu, thêm tiếp (toạ độ minh hoạ)
  { id: "q6", left: 77, top: 94.0, width: 26, answer: "silver" },
  { id: "q7", left: 77, top: 105.5, width: 26, answer: "maths" },
  { id: "q8", left: 77, top: 117.0, width: 26, answer: "wool" },
  { id: "q9", left: 77, top: 128.5, width: 26, answer: "a museum" },
  { id: "q10", left: 77, top: 140.0, width: 26, answer: "a factory" }
];
