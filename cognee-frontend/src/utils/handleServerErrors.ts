export default function handleServerErrors(response: Response, retry?: (response: Response) => Promise<Response>, useCloud?: boolean): Promise<Response> {
  return new Promise((resolve, reject) => {
    if (response.status === 401 && !useCloud) {
      // 对于 401 错误,先尝试重试(如果有 retry 函数)
      // 只有在重试失败后才重定向到登录页
      // 这样可以解决登录后 cookie 还未完全设置的问题
      
      if (retry) {
        return retry(response)
          .catch(() => {
            // 重试失败,重定向到登录页
            if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/auth')) {
              // 只有当前不在认证页面时才重定向
              window.location.href = '/auth/login';
            }
            return Promise.reject({ message: 'Unauthorized', status: 401 });
          });
      } else {
        // 没有 retry 函数,直接抛出错误,不重定向
        // 让调用者决定如何处理
        return Promise.reject({ message: 'Unauthorized', status: 401 });
      }
    }
    if (!response.ok) {
      return response.json().then(error => {
        error.status = response.status;
        reject(error);
      });
    }

    if (response.status >= 200 && response.status < 300) {
      return resolve(response);
    }

    return reject(response);
  });
}
