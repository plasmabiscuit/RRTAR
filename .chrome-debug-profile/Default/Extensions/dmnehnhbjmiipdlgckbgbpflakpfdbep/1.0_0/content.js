function extractReadableContent() {
    // 使用当前文档创建一个新的 Readability 对象
    const readable = new Readability(document.cloneNode(true));
  
    // 调用 parse() 函数提取正文内容
    const article = readable.parse();
  
    // 返回提取的正文内容
    return article.content;
  }
  
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'requestReadableContent') {
      const content = extractReadableContent();
      // 如果 sendResponse 回调函数没有被调用，则返回一个默认值
      setTimeout(() => {
        if (!sendResponse.called) {
          sendResponse({ type: 'readableContent', content: 'Please reload the Page to extract the content' });
        }
      }, 1000);
      // sendResponse 回调函数被调用时返回正常响应
      sendResponse({ type: 'readableContent', content: content, called: true });
      return true;
    }
  });
  