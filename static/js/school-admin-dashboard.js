document.addEventListener("DOMContentLoaded", () => {
  const filterButtons = document.querySelectorAll("[data-filter]");
  const rows = document.querySelectorAll(".activity-row");

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const selected = button.dataset.filter;
      filterButtons.forEach((item) => item.classList.toggle("selected", item === button));
      rows.forEach((row) => {
        row.hidden = selected !== "all" && row.dataset.status !== selected;
      });
    });
  });

  const modal = document.getElementById("status-modal");
  if (!modal) return;

  const studentId = document.getElementById("modal-student-id");
  const studentLabel = document.getElementById("modal-student-label");
  const reason = document.getElementById("modal-reason");

  document.querySelectorAll("[data-student-id]").forEach((button) => {
    button.addEventListener("click", () => {
      studentId.value = button.dataset.studentId;
      studentLabel.textContent = `${button.dataset.studentName} · ${button.dataset.studentNumber}`;
      reason.value = "";
      modal.hidden = false;
      document.getElementById("modal-status").focus();
    });
  });

  const closeModal = () => { modal.hidden = true; };
  modal.querySelectorAll("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", closeModal);
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
});
