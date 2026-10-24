using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Text;
using System.Windows.Forms;

namespace LVClient {
    public partial class Login : Form {
        public Login() {
            InitializeComponent();
        }

        private void Login_Load(object sender, EventArgs e) {
            txtUsername.Text = LVClient.Web.LVWeb.lvusername;
            txtLvPassword.Text = LVClient.Web.LVWeb.lvpassword;
            if (txtLvPassword.Text != "") XLogin();
        }

        private void wbLogin_DocumentCompleted(object sender, WebBrowserDocumentCompletedEventArgs e) {
            if (LVClient.Web.LVWeb.loadinput == false) {
                if (wbLogin.Url.AbsolutePath == "/login.aspx") {
                    timer1.Enabled = true;
                    LVClient.Web.LVWeb.loadinput = true;
                }
            }
            if (wbLogin.Url.AbsolutePath == "/play.aspx") {
                //timer1.Enabled = false;
                //wbLogin.Document.Cookie = "";
                lock (LVClient.Web.LVWeb.islock) 
				{
                    LVClient.Web.LVWeb.LoginHtml = wbLogin.Document.Body.InnerHtml;
                    //wbLogin.Document.Forms[0].OuterHtml = "";
                }
                //if (LVClient.Web.LVWeb.firstlogin) {
                    //FirstLogin();
                    //tbLogin.Select();
                //}
                //wbLogin.Navigate("about:blank");
                //wbLogin.Document.Cookie = "";
                //tbFirstLogin.Controls.Remove(wbLogin);
                //wbLogin = null;
                //wbLogin = new WebBrowser();
                //wbLogin.DocumentCompleted +=new WebBrowserDocumentCompletedEventHandler(wbLogin_DocumentCompleted);
                //tbFirstLogin.Controls.Add(wbLogin);

                //tbFirstLogin.Controls.Add(wbLogin);
                LVClient.Web.LVWeb.lvusername= txtUsername.Text;
                LVClient.Web.LVWeb.lvpassword= txtLvPassword.Text;
                this.Close();
            }
        }

        private void timer1_Tick(object sender, EventArgs e) {
            try {
                wbLogin.Document.Forms[0].All["TxtUserName"].SetAttribute("value", txtUsername.Text);
                wbLogin.Document.Forms[0].All["TxtPass"].SetAttribute("value", txtLvPassword.Text);
                HtmlElement x = wbLogin.Document.CreateElement("input");
                x.Name = "imgLoginLogOut.x";
                x.SetAttribute("value", "39");
                HtmlElement y = wbLogin.Document.CreateElement("input");
                y.Name = "imgLoginLogOut.y";
                y.SetAttribute("value", "7");
                wbLogin.Document.Forms[0].InsertAdjacentElement(HtmlElementInsertionOrientation.BeforeEnd, x);
                wbLogin.Document.Forms[0].InsertAdjacentElement(HtmlElementInsertionOrientation.BeforeEnd, y);
                wbLogin.Document.Forms[0].InvokeMember("submit");
                timer1.Enabled = false;
            } catch (Exception ex) {
            }
        }

        private void cmdLogin_Click(object sender, EventArgs e) {
            //Common.common.ClearCookies();
            LVClient.Web.LVWeb.loadinput = false;
            wbLogin.Navigate("http://login.linhvuong.zooz.vn/login.aspx?server=" + LVClient.Web.LVWeb.Server, "", null, "Referer: http://linhvuong.zooz.vn/news/\n");
            
        }
        public void XLogin() {
            LVClient.Web.LVWeb.loadinput = false;
            wbLogin.Navigate("http://login.linhvuong.zooz.vn/login.aspx?server=" + LVClient.Web.LVWeb.Server, "", null, "Referer: http://linhvuong.zooz.vn/news/\n");
        }
        private void cboServer_SelectedIndexChanged(object sender, EventArgs e) {
            LVClient.Web.LVWeb.Server = int.Parse(cboServer.Text.Substring(0, 1));
        }
    }
}