(() => {
  const messageSelector = [
    ".student-message--success",
    ".student-message--error",
    ".message.success",
    ".message.error",
    ".message--success",
    ".message--error",
  ].join(", ");
  const scheduledMessages = new WeakSet();

  function scheduleDismissal() {
    document.querySelectorAll(messageSelector).forEach((message) => {
      if (scheduledMessages.has(message)) return;
      scheduledMessages.add(message);
      window.setTimeout(() => {
        if (message.isConnected) message.remove();
      }, 3000);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleDismissal, { once: true });
  } else {
    scheduleDismissal();
  }
  document.addEventListener("turbo:load", scheduleDismissal);
})();
