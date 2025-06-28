function startTimer(duration, display, form) {
  let timer = duration;

  const tick = () => {
    const minutes = String(Math.floor(timer / 60)).padStart(2, "0");
    const seconds = String(timer % 60).padStart(2, "0");
    display.textContent = `Time left: ${minutes}:${seconds}`;

    if (timer-- <= 0) {
      clearInterval(intervalId);
      window.__submitted__ = true;        // để script chặn Back biết đã nộp
      form.submit();                      // POST tới /submit → trang kết quả
    }
  };

  tick();                                 // hiển thị ngay giây đầu
  const intervalId = setInterval(tick, 1_000);
}
