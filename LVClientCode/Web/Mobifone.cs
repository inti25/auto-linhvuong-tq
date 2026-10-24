using System;
using System.Collections.Generic;
using System.Text;
using System.Net;
namespace LVClient.Web {
    class Mobifone : SMS {
        public bool Login(string username, string password) {
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create("http://www.mobifone.com.vn/web/vn/users/authenticate.jsp");
            req.GetRequestStream();
            return true;
        }
        public bool Send(string to, string mess) {
            return true;
        }
    }
}
