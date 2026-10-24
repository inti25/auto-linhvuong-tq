using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace LVClient.LVThread {
    class LOADING {
        delegate void SetTextCallback(string text);
        public Thread InThread; public string threadID;
        public bool IsRun = false;
        public Form f;
        public string oldtext;
        public void run() 
		{
            oldtext = f.Text;
            IsRun = true;
            SetText("Đang pause - Nhấn Ctrl+Q để chạy lại");
            //lock (LVClient.Web.LVWeb.ispause) {
                
                Thread.Sleep(300000);
                SetText(oldtext);
            //}
        }
        public void Auto() {
            InThread = new Thread(new ThreadStart(run));
            IsRun = true;  InThread.Start();
        }
        public void Stop() {
            if (IsRun) {
                InThread.Abort();
                InThread.Join();  Common.ThreadManager.RemoveThread(threadID);
                f.Text = oldtext;
                IsRun = false;
            }
        }
        private void SetText(String str) {
            if (this.f.InvokeRequired) {
                SetTextCallback d = new SetTextCallback(SetText);
                this.f.Invoke(d, new object[] { str });
            } else {
                this.f.Text = str;
            }
        }
    }
}
