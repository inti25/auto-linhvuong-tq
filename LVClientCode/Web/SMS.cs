using System;
using System.Collections.Generic;
using System.Text;
using System.Net;
namespace LVClient.Web {
    interface SMS {
        //public System.Net.CookieContainer cookies;
        bool Login(string username, string password);
        bool Send(string to, string mess);
    }
}
