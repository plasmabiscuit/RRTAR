// 需要引入 Turndown 库（用于导出 Markdown）和 jsPDF 库（用于导出 PDF）

const turndownService = new TurndownService();

// 在弹出窗口加载完成后请求可读内容并为按钮添加事件监听器
window.addEventListener("load", () => {
  requestReadableContent();

  document.getElementById("exportMD").addEventListener("click", () => {
    exportMarkdown();
  });
  document.getElementById("exportPDF").addEventListener("click", function () {
    const content = document.getElementById("content");
    // 等待所有图片加载完成
    waitForImagesToLoad(content).then(() => {
      const opt = {
        margin: 1,
        filename: "content.pdf",
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
      };

      html2pdf().set(opt).from(content).save();
    });
  });
});

function waitForImagesToLoad(element) {
  const images = element.querySelectorAll("img");

  // 检查每个图片的加载状态
  const checkImage = (img) =>
    new Promise((resolve) => {
      if (img.complete) {
        resolve();
      } else {
        img.addEventListener("load", () => resolve());
        img.addEventListener("error", () => resolve());
      }
    });

  // 等待所有图片加载完成
  const promises = Array.from(images).map((img) => checkImage(img));
  return Promise.all(promises);
}

// 请求可读内容并显示
function requestReadableContent() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const activeTab = tabs[0];
    chrome.tabs.sendMessage(
      activeTab.id,
      { type: "requestReadableContent" },
      (response) => {
        const contentElement = document.getElementById("content");

        // 检查 response 是否为 undefined
        if (response === undefined) {
          contentElement.innerHTML = "Please refresh to extract the content!";
        } else if (response.type === "readableContent") {
          contentElement.innerHTML = response.content;
        } else {
          contentElement.innerHTML =
            "Unable to extract content. Please try again.";
        }
      }
    );
  });
}

function exportMarkdown() {
  const contentElement = document.getElementById("content");
  const markdown = turndownService.turndown(contentElement.innerHTML);
  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "content.md";
  a.click();
  URL.revokeObjectURL(url);
}
