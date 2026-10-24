/*
 *  Authors:  Benton Stark
 * 
 *  Copyright (c) 2007-2009 Starksoft, LLC (http://www.starksoft.com) 
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 * 
 */

using System;
using System.Collections.Generic;
using System.Text;

namespace LVClient.Connection.StarksoftProxy
{
    /// <summary>
    /// The type of proxy.
    /// </summary>
    public enum ProxyType
    {
        /// <summary>
        /// No Proxy
        /// </summary>
        None,
        /// <summary>
        /// HTTP Proxy
        /// </summary>
        Http,
        /// <summary>
        /// SOCKS v4 Proxy
        /// </summary>
        Socks4,
        /// <summary>
        /// SOCKS v4a Proxy
        /// </summary>
        Socks4a,
        /// <summary>
        /// SOCKS v5 Proxy
        /// </summary>
        Socks5
    }

    /// <summary>
    /// Factory class for creating new proxy client objects.
    /// </summary>
    /// <remarks>
    /// <code>
    /// // create an instance of the client proxy factory
    /// ProxyClientFactory factory = new ProxyClientFactory();
    ///        
	/// // use the proxy client factory to generically specify the type of proxy to create
    /// // the proxy factory method CreateProxyClient returns an IProxyClient object
    /// IProxyClient proxy = factory.CreateProxyClient(ProxyType.Http, "localhost", 6588);
    ///
	/// // create a connection through the proxy to www.starksoft.com over port 80
    /// System.Net.Sockets.TcpClient tcpClient = proxy.CreateConnection("www.starksoft.com", 80);
    /// </code>
    /// </remarks>
    public class ProxyClientFactory
    {
        /// <summary>
        /// Factory method for creating new proxy client objects.
        /// </summary>
        /// <param name="type">The type of proxy client to create.</param>
        /// <param name="proxyHost">The proxy host or IP address.</param>
        /// <param name="proxyPort">The proxy port number.</param>
        /// <returns></returns>
		public IProxyClient CreateProxyClient(ProxyType type, string proxyHost, int proxyPort)
        {
            switch (type)
            {
				case ProxyType.Http:
                    return new HttpProxyClient(proxyHost, proxyPort);

				case ProxyType.Socks4:
                    return new Socks4ProxyClient(proxyHost, proxyPort);

				case ProxyType.Socks4a:
                    return new Socks4aProxyClient(proxyHost, proxyPort);

				case ProxyType.Socks5:
                    return new Socks5ProxyClient(proxyHost, proxyPort);
            
                default:
                    return null;
            }
        }
    
    }



}
