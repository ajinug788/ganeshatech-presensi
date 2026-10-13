(() => {
  const closeOpenMenus = () => {
    document.querySelectorAll(".student-account-menu[open]").forEach((menu) => {
      menu.open = false;
    });
  };

  document.addEventListener("click", (event) => {
    document.querySelectorAll(".student-account-menu[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeOpenMenus();
  });

  document.addEventListener("turbo:before-cache", closeOpenMenus);
})();
